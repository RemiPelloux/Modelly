"""Property layers: numpy arrays attached to a grid and exposed on its cells.

A property layer is one ``np.ndarray`` shaped like the grid. The grid exposes it
as an attribute (``grid.sugar``) and every cell of that grid gets an accessor
(``cell.sugar``) that reads and writes the array at the cell's coordinate, so
vectorised updates on the array and per-cell reads stay in sync for free.
"""

from __future__ import annotations

from itertools import chain

import numpy as np

EMPTY_LAYER = "empty"


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

        if name in self.__dict__ or any(name in c.__dict__ for c in type(self).__mro__):
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

        def getter(self_cell):
            return array[self_cell.coordinate]

        def setter(self_cell, value):
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
