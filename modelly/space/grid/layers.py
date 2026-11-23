"""Property layers: numpy arrays attached to a grid and exposed on its cells.

A property layer is one ``np.ndarray`` shaped like the grid. The grid exposes it
as an attribute (``grid.sugar``) and every cell of that grid gets an accessor
(``cell.sugar``) that reads and writes the array at the cell's coordinate, so
vectorised updates on the array and per-cell reads stay in sync for free.
"""

from __future__ import annotations

from itertools import chain
from typing import Any

import numpy as np

from modelly._native.cells import EmptyFlag
from modelly.core.column_access import WRITE_ERRORS

EMPTY_LAYER = "empty"


def _layer_view(array: np.ndarray) -> Any:
    """A ``memoryview`` of ``array`` that a coordinate tuple indexes, else ``array``.

    Read through it, a cell gets a Python ``float``, ``int`` or ``bool`` (as a Column
    does), which is cheaper to read and several times cheaper to compute with than a
    numpy scalar. Dtypes a memoryview cannot index keep numpy's scalars.
    """
    try:
        view = memoryview(array)
        view[(0,) * array.ndim]  # probes that the format can be indexed
    except (TypeError, ValueError, NotImplementedError, BufferError, IndexError):
        return array
    return view


def _empty_accessor(array: np.ndarray) -> Any:
    """``cell.empty`` on a grid: the "empty" layer, kept in step with the empties index.

    Every move that empties or fills a cell writes it. The compiled ``EmptyFlag`` does
    what the property below does, in C, when it is built and takes ``array``.
    """
    view = _layer_view(array)

    def getter(self_cell):
        return view[self_cell.coordinate]

    def setter(self_cell, value):
        view[self_cell.coordinate] = value
        index = self_cell._empties_index
        if index is not None:
            index.set_empty(self_cell, value)

    accessor = property(getter, setter, doc=f"property_layer '{EMPTY_LAYER}'")
    if EmptyFlag is None:
        return accessor
    try:
        return EmptyFlag(array, accessor)
    except (TypeError, ValueError, BufferError):  # read-only or unusual: the property
        return accessor


class HasPropertyLayers:
    """Mixin giving a grid named property layers backed by numpy arrays.

    Expects the host to define ``dimensions`` (the array shape), ``cell_klass``
    (a class private to the grid, since accessors are installed on it),
    ``property_layers`` and ``_read_only_layers``.
    """

    dimensions: tuple[int, ...]
    cell_klass: type
    property_layers: dict[str, np.ndarray]
    _read_only_layers: set[str]

    def create_property_layer(
        self,
        name: str,
        default_value=0.0,
        dtype=float,
        read_only: bool = False,
    ) -> np.ndarray:
        """Create a property layer array and attach it to cells.

        Warning:
        Do not reassign `grid.name` directly — this will detach it from
        `property_layers` and break cell-level access. Use in-place operations.

            grid.sugar[:] = 0    # correct
            grid.sugar = array   # wrong — breaks cell access
        """
        array = np.full(self.dimensions, default_value, dtype=dtype)
        self._attach_property_layer(name, array, read_only=read_only)
        return array

    def add_property_layer(
        self, name: str, array: np.ndarray, read_only: bool = False
    ) -> None:
        """Attach an existing array as a property layer.  Shape must match `self.dimensions`.

        Warning:
        Do not reassign `grid.name` directly — this will detach it from
        `property_layers` and break cell-level access. Use in-place operations.

            grid.sugar[:] = 0    # correct
            grid.sugar = array   # wrong — breaks cell access
        """
        if tuple(array.shape) != tuple(self.dimensions):
            raise ValueError(
                f"Array shape {array.shape} does not match grid dimensions {self.dimensions}."
            )
        self._attach_property_layer(name, array, read_only=read_only)

    def remove_property_layer(self, name: str) -> None:
        """Remove a property_layer and its grid and cell attributes.

        Args:
            name: property_layer name.
        """
        if name not in self.property_layers:
            raise KeyError(f"No property_layer named '{name}'.")
        del self.property_layers[name]
        delattr(self, name)
        delattr(self.cell_klass, name)
        self.cell_klass.property_layers.discard(name)
        self._read_only_layers.discard(name)

    def _attach_property_layer(
        self, name: str, array: np.ndarray, read_only: bool = False
    ) -> None:
        self._check_layer_name(name)
        self.property_layers[name] = array
        setattr(self, name, array)
        self._install_layer_accessor(name, array, read_only)
        self.cell_klass.property_layers.add(name)
        if read_only:
            self._read_only_layers.add(name)

    def _check_layer_name(self, name: str) -> None:
        """Reject a layer name that already exists or would shadow an attribute."""
        if name in self.property_layers:
            raise ValueError(f"property_layer '{name}' already exists.")

        # hasattr, not self.__dict__: reading __dict__ costs the grid the
        # interpreter's fast attribute loads on CPython 3.13+.
        if hasattr(self, name) or any(name in c.__dict__ for c in type(self).__mro__):
            raise ValueError(
                f"property_layer '{name}' conflicts with an existing Grid attribute."
            )

        # Attaching a layer installs an accessor on cell_klass via setattr, so any
        # name already defined on that class would be silently shadowed. Walking
        # __mro__ __dict__ covers @property accessors, methods, plain class vars,
        # and __slots__ members alike (a slot is a member_descriptor living in the
        # class __dict__). "empty" is exempt: Grid.__init__ itself installs it as
        # a property layer backing Cell.empty.
        cell_attrs = set(
            chain.from_iterable(c.__dict__ for c in self.cell_klass.__mro__)
        )
        if name != EMPTY_LAYER and name in cell_attrs:
            raise ValueError(
                f"property_layer '{name}' conflicts with an existing "
                f"{self.cell_klass.__name__} attribute."
            )

    def _install_layer_accessor(
        self, name: str, array: np.ndarray, read_only: bool
    ) -> None:
        """Install ``cell.<name>`` on the grid's cell class, reading/writing ``array``."""
        view = _layer_view(array)

        def getter(self_cell):
            return view[self_cell.coordinate]

        def setter(self_cell, value):
            # A memoryview write is about a third cheaper; it refuses some writes
            # numpy accepts (a float into an int layer, a read-only array), which
            # then go to numpy.
            try:
                view[self_cell.coordinate] = value
            except WRITE_ERRORS:
                array[self_cell.coordinate] = value

        accessor = (
            property(getter, doc=f"property_layer '{name}'")
            if read_only
            else property(getter, setter, doc=f"property_layer '{name}'")
        )
        setattr(self.cell_klass, name, accessor)

    def _restore_layer_accessors(self) -> None:
        """Re-install every layer accessor after unpickling.

        Read-only layers (tracked in ``_read_only_layers``) are restored without a
        setter so the read-only constraint survives the round trip.
        """
        # Older pickles may predate _read_only_layers; default to no read-only layers.
        self._read_only_layers = getattr(self, "_read_only_layers", set())
        for name, array in self.property_layers.items():
            self._install_layer_accessor(name, array, name in self._read_only_layers)
