"""The base class shared by every grid, plus its empty-cell index.

Concrete connection patterns (Moore, Von Neumann, hexagonal) live in
:mod:`modelly.space.grid.grids`.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import product
from random import Random
from typing import Any, TypeVar

import numpy as np

from modelly.space.base import DiscreteSpace
from modelly.space.cells.cell import Cell
from modelly.space.cells.collection import CellCollection
from modelly.space.grid.cell_class import (  # noqa: F401 - re-exported for old pickles
    _make_grid_cell_class,
    pickle_gridcell,
    unpickle_gridcell,
)
from modelly.space.grid.layers import EMPTY_LAYER, HasPropertyLayers

T = TypeVar("T", bound=Cell)

# Draws tried before scanning the grid for a cell with spare capacity.
CAPACITY_SAMPLE_TRIES = 50
GRID_2D = 2


class Grid(HasPropertyLayers, DiscreteSpace[T]):
    """Base class for all grid classes.

    Attributes:
        dimensions (Sequence[int]): the dimensions of the grid
        torus (bool): whether the grid is a torus
        capacity (int): the capacity of a grid cell
        random (Random): the random number generator
        _try_random (bool): whether to get empty cell be repeatedly trying random cell

    Notes:
        width and height are accessible via property_layers, higher dimensions can be retrieved via dimensions

    """

    @property
    def width(self) -> int:
        """Convenience access to the width of the grid."""
        return self.dimensions[0]

    @property
    def height(self) -> int:
        """Convenience access to the height of the grid."""
        return self.dimensions[1]

    def __init__(
        self,
        dimensions: Sequence[int],
        torus: bool = False,
        capacity: float | None = None,
        random: Random | None = None,
        cell_klass: type[T] = Cell,
    ) -> None:
        """Initialise the grid class.

        Args:
            dimensions: the dimensions of the space
            torus: whether the space wraps
            capacity: capacity of the grid cell
            random: a random number generator
            cell_klass: the base class to use for the cells
        """
        super().__init__(capacity=capacity, random=random, cell_klass=cell_klass)
        self.torus = torus
        self.dimensions = dimensions
        self._try_random = True
        self._ndims = len(dimensions)
        self._validate_parameters()
        self.cell_klass = _make_grid_cell_class(self.cell_klass)
        self.property_layers: dict[str, np.ndarray] = {}
        # Track which property layers are read-only so the constraint survives
        # pickling and deepcopy (see __getstate__/__setstate__).
        self._read_only_layers: set[str] = set()

        coordinates = product(*(range(dim) for dim in self.dimensions))

        self._cells = {
            coord: self.cell_klass(coord, capacity=capacity, random=self.random)
            for coord in coordinates
        }
        self._celllist = list(self._cells.values())
        self._connect_cells()
        self.create_property_layer(EMPTY_LAYER, default_value=True, dtype=bool)
        self._install_empty_accessor()

    def _install_empty_accessor(self) -> None:
        """Back ``cell.empty`` with the "empty" layer and keep the empties index in sync."""
        array = self.property_layers[EMPTY_LAYER]

        def getter(self_cell):
            return array[self_cell.coordinate]

        def setter(self_cell, value):
            array[self_cell.coordinate] = value
            index = self_cell._empties_index
            if index is not None:
                index.set_empty(self_cell, value)

        setattr(
            self.cell_klass,
            EMPTY_LAYER,
            property(getter, setter, doc=f"property_layer '{EMPTY_LAYER}'"),
        )

    def get_neighborhood_mask(
        self, coordinate, include_center: bool = True, radius: int = 1
    ) -> np.ndarray:
        """Return a boolean mask shaped like ``self.dimensions`` for a neighborhood."""
        cell = self._cells[coordinate]
        neighborhood = cell.get_neighborhood(
            include_center=include_center, radius=radius
        )
        mask = np.zeros(self.dimensions, dtype=bool)
        coords = np.array([c.coordinate for c in neighborhood])
        if coords.size:
            mask[tuple(coords[:, i] for i in range(coords.shape[1]))] = True
        return mask

    def find_nearest_cell(self, position: np.ndarray) -> T:
        """Find the cell containing the given position.

        Args:
            position: Physical position [x, y]

        Returns:
            Cell: The cell containing the position

        Raises:
            ValueError: If position is outside grid bounds and not a torus
        """
        # Floor to get cell coordinate
        coord = tuple(np.floor(position).astype(int))

        # Handle torus wrapping
        if self.torus:
            coord = tuple(c % d for c, d in zip(coord, self.dimensions))

        # Check bounds for non-torus grids
        elif not all(0 <= c < d for c, d in zip(coord, self.dimensions)):
            raise ValueError(
                f"Position {position} is outside grid bounds. "
                f"Dimensions: {self.dimensions}"
            )

        return self._cells[coord]

    def _connect_cells(self) -> None:
        if self._ndims == GRID_2D:
            self._connect_cells_2d()
        else:
            self._connect_cells_nd()

    def _connect_cells_2d(self) -> None:
        raise NotImplementedError(  # pragma: no cover
            f"{type(self).__name__} does not implement _connect_cells_2d(). "
        )

    def _connect_cells_nd(self) -> None:
        raise NotImplementedError(  # pragma: no cover
            f"{type(self).__name__} does not implement _connect_cells_nd(). "
        )

    def _validate_parameters(self):
        if not all(isinstance(dim, int) and dim > 0 for dim in self.dimensions):
            raise ValueError("Dimensions must be a list of positive integers.")
        if not isinstance(self.torus, bool):
            raise TypeError("Torus must be a boolean.")
        if self.capacity is not None and not isinstance(self.capacity, float | int):
            raise TypeError("Capacity must be a number or None.")

    @property
    def cells_with_capacity(self) -> CellCollection[T]:
        """Return all cells that have available capacity (i.e. are not full).

        A cell is considered *available* if ``not cell.is_full``.

        This is meaningfully different from :attr:`~DiscreteSpace.empties`:
        ``empties`` only includes cells with **zero** agents. If a cell has
        ``capacity=5`` and currently holds 3 agents it is **not** empty, but it
        **is** still available. ``cells_with_capacity`` is therefore the correct
        API for models where agents share cells up to a finite limit.

        For cells with ``capacity=None`` (unlimited), every cell is always
        available regardless of how many agents it holds.

        Returns:
            CellCollection[T]: All cells where ``len(agents) < capacity``
            (or all cells when capacity is None).

        Example::

            # Place an agent in any non-full cell
            agent.move_to(grid.select_random_cell_with_capacity())

            # Count how many cells still have room
            len(list(grid.cells_with_capacity))
        """
        if self.capacity is None:
            return self.all_cells
        return self.all_cells.select(lambda cell: not cell.is_full)

    def select_random_cell_with_capacity(self) -> Cell:
        """Select a random cell that has remaining capacity.

        Raises:
            IndexError: If every cell in the grid is at full capacity.

        Example::

            # Safe placement that respects capacity limits
            free_cell = grid.select_random_cell_with_capacity()
            agent.move_to(free_cell)
        """
        random = self.random
        cells = self._celllist
        # Fast path: random draws, O(1) average when the grid is sparse.
        # Fallback: build the explicit list, O(n) (see select_random_empty_cell).
        if self._try_random:
            for _ in range(CAPACITY_SAMPLE_TRIES):
                cell = random.choice(cells)
                if not cell.is_full:
                    return cell

        available = list(self.cells_with_capacity)
        if not available:
            raise IndexError(
                "No available cells exist in the grid: all cells are at full capacity."
            )
        return random.choice(available)

    # The two connectors below write ``cell.connections`` directly: the cells are
    # fresh, so there is no neighborhood cache to clear, and the per-connection
    # method call is most of the construction time of a large grid.

    def _connect_single_cell_nd(self, cell: T, offsets: list[tuple[int, ...]]) -> None:
        coord = cell.coordinate
        dimensions = self.dimensions
        cells = self._cells
        connections = cell.connections

        for d_coord in offsets:
            n_coord = tuple(c + dc for c, dc in zip(coord, d_coord))
            if self.torus:
                n_coord = tuple(nc % d for nc, d in zip(n_coord, dimensions))
            if all(0 <= nc < d for nc, d in zip(n_coord, dimensions)):
                connections[d_coord] = cells[n_coord]

    def _connect_single_cell_2d(self, cell: T, offsets: list[tuple[int, int]]) -> None:
        i, j = cell.coordinate
        height, width = self.dimensions
        cells = self._cells
        connections = cell.connections

        if self.torus:
            for offset in offsets:
                di, dj = offset
                connections[offset] = cells[(i + di) % height, (j + dj) % width]
            return
        for offset in offsets:
            di, dj = offset
            ni, nj = i + di, j + dj
            if 0 <= ni < height and 0 <= nj < width:
                connections[offset] = cells[ni, nj]

    def __getstate__(self) -> dict[str, Any]:
        """Drop the per-grid cell class; it is rebuilt on load."""
        state = super().__getstate__()
        return {k: v for k, v in state.items() if k != "cell_klass"}

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore state and re-attach property_layer accessors to the cell class.

        Each unpickled cell arrives with its own freshly created class, so all
        cells are re-homed onto one class before the accessors are installed on it.
        """
        super().__setstate__(state)
        for cell in self._cells.values():
            cell.__class__ = self.cell_klass
        self._restore_layer_accessors()
        if EMPTY_LAYER in self.property_layers:
            self._install_empty_accessor()
