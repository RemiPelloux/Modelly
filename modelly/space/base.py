"""Abstract Base class for building cell-based spatial environments.

DiscreteSpace provides the core functionality needed by all cell-based spaces:
- Cell creation and tracking
- Agent-cell relationship management
- Property Layer support
- Random selection capabilities
- Capacity management

This serves as the foundation for specific space implementations like grids
and networks, ensuring consistent behavior and shared functionality across
different space types. All concrete cell space implementations (grids, networks, etc.)
inherit from this class.
"""

from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from collections.abc import Iterator
from functools import cached_property
from random import Random
from typing import TYPE_CHECKING, TypeVar

import numpy as np

from modelly.core.agent import AgentSet
from modelly.core.exceptions import CellMissingException
from modelly.space.cells.cell import Cell
from modelly.space.cells.collection import CellCollection
from modelly.space.cells.empties import _EmptiesIndex

if TYPE_CHECKING:
    from modelly.space.cells.agents import CellAgent
    from modelly.space.cells.index import CellIndex

T = TypeVar("T", bound=Cell)

# Random draws tried before building the empties index. Each draw is O(1), so a
# sparse space answers in a draw or two; a dense space fails them all once, pays
# for one O(n) index build, and answers in O(1) ever after.
EMPTY_SAMPLE_TRIES = 8


def space_agents(space: DiscreteSpace) -> Iterator[CellAgent]:
    """The agents in the cells' lists, then those a CellIndex tracks by row column."""
    yield from space.all_cells.agents
    if space._cell_index is not None:
        yield from space._cell_index.tracked_agents()


class DiscreteSpace[T: Cell](ABC):
    """Base class for all discrete spaces.

    Attributes:
        capacity (int): The capacity of the cells in the discrete space
        all_cells (CellCollection): The cells composing the discrete space
        random (Random): The random number generator
        cell_klass (Type) : the type of cell class
        empties (CellCollection) : collection of all cells that are empty
        property_layers (dict[str, np.ndarray]): property_layer of the discrete space

    Notes:
        A `UserWarning` is issued if `random=None`. You can resolve this warning by explicitly
        passing a random number generator. In most cases, this will be the seeded random number
        generator in the model. So, you would do `random=self.random` in a `Model` or `Agent` instance.

    """

    # Set by a CellIndex built on this space (see CellIndex.track).
    _cell_index: CellIndex | None = None

    def __init__(
        self,
        capacity: int | None = None,
        cell_klass: type[T] = Cell,
        random: Random | None = None,
    ):
        """Instantiate a DiscreteSpace.

        Args:
            capacity: capacity of cells
            cell_klass: base class for all cells
            random: random number generator
        """
        super().__init__()
        self.capacity = capacity
        self._cells: dict[tuple[int, ...], T] = {}
        if random is None:
            warnings.warn(
                "Random number generator not specified, this can make models non-reproducible. Please pass a random number generator explicitly",
                UserWarning,
                stacklevel=2,
            )
            random = Random()
        self.random = random
        self.cell_klass = cell_klass
        self._empties = _EmptiesIndex()
        self._try_random = True

    @property
    def agents(self) -> AgentSet:
        """Return an AgentSet with the agents in the space, row-placed ones included."""
        return AgentSet(space_agents(self), random=self.random)

    @abstractmethod
    def _connect_cells(self) -> None: ...

    @abstractmethod
    def find_nearest_cell(self, position: np.ndarray) -> T:
        """Find the cell at or nearest to the given position."""

    def _reset_empties(self) -> None:
        """Forget the empties index; it is rebuilt on the next request."""
        for cell in self._cells.values():
            cell._empties_index = None
        self._empties = _EmptiesIndex()

    def add_cell(self, cell: T):
        """Add a cell to the space.

        Args:
            cell: cell to add

        Note:
            Discrete spaces rely on caching neighborhood relations for speedups. Adding or removing cells and
            connections at runtime is possible. However, only the caches of cells directly affected will be cleared. So
            if you rely on getting neighborhoods of cells with a radius higher than 1, these might not be cleared
            correctly if you are adding or removing cells and connections at runtime.

        Warning:
            Coordinate Collision: If a cell already exists at the specified
            coordinates (e.g., cell1), it will be overwritten silently by the
            new cell (cell2).

            Ensure the target coordinates are vacant before calling this method.
        """
        self.__dict__.pop("all_cells", None)
        self._cells[cell.coordinate] = cell
        self._reset_empties()

    def remove_cell(self, cell: T):
        """Remove a cell from the space.

        Note:
            Discrete spaces rely on caching neighborhood relations for speedups. Adding or removing cells and
            connections at runtime is possible. However, only the caches of cells directly affected will be cleared. So
            if you rely on getting neighborhoods of cells with a radius higher than 1, these might not be cleared
            correctly if you are adding or removing cells and connections at runtime.


        """
        neighbors = cell.neighborhood

        try:
            self._cells.pop(cell.coordinate)
        except KeyError as e:
            raise CellMissingException(cell.coordinate) from e

        self.__dict__.pop("all_cells", None)
        self._reset_empties()

        # iterate over all neighbors
        for neighbor in neighbors.cells:
            neighbor.disconnect(cell)
            cell.disconnect(neighbor)

    def add_connection(self, cell1: T, cell2: T):
        """Add a connection between the two cells.

        Note:
            Discrete spaces rely on caching neighborhood relations for speedups. Adding or removing cells and
            connections at runtime is possible. However, only the caches of cells directly affected will be cleared. So
            if you rely on getting neighborhoods of cells with a radius higher than 1, these might not be cleared
            correctly if you are adding or removing cells and connections at runtime.

        """
        cell1.connect(cell2)
        cell2.connect(cell1)

    def remove_connection(self, cell1: T, cell2: T):
        """Remove a connection between the two cells.

        Note:
            Discrete spaces rely on caching neighborhood relations for speedups. Adding or removing cells and
            connections at runtime is possible. However, only the caches of cells directly affected will be cleared. So
            if you rely on getting neighborhoods of cells with a radius higher than 1, these might not be cleared
            correctly if you are adding or removing cells and connections at runtime.

        """
        cell1.disconnect(cell2)
        cell2.disconnect(cell1)

    @cached_property
    def all_cells(self):
        """Return all cells in space."""
        return CellCollection(
            {cell: cell._agents for cell in self._cells.values()}, random=self.random
        )

    def __iter__(self):  # noqa
        return iter(self._cells.values())

    def __getitem__(self, key: tuple[int, ...]) -> T:  # noqa: D105
        try:
            return self._cells[key]
        except KeyError as e:
            raise CellMissingException(key) from e

    @property
    def empties(self) -> CellCollection[T]:
        """Return all empty in spaces."""
        return self.all_cells.empties

    def select_random_empty_cell(self) -> T:
        """Select a random empty cell.

        Sparse spaces are answered by a few random draws. The first time the draws
        all fail (or when ``_try_random`` is False) the space builds an index of
        its empty cells, kept current by ``cell.empty`` from then on, so every
        later call is O(1) regardless of how full the space is.

        Raises:
            ValueError: If the space has no empty cell.
        """
        empties = self._empties
        if not empties.enabled:
            cells = self.all_cells.cells
            if self._try_random:
                random = self.random
                for _ in range(EMPTY_SAMPLE_TRIES):
                    cell = random.choice(cells)
                    if not cell._agents:
                        return cell
            empties.build(cells)

        try:
            return empties.choice(self.random)
        except IndexError as e:
            raise ValueError(
                f"{type(self).__name__} is completely full. No empty cells available. "
                "Cannot select a random empty cell."
            ) from e

    def __setstate__(self, state):
        """Set the state of the discrete space and rebuild the connections."""
        self.__dict__ = state
        self._empties = _EmptiesIndex()

        if self._cells:
            self.cell_klass = type(next(iter(self._cells.values())))

        for cell in self._cells.values():
            cell.connections = {
                key: self._cells[coord] for key, coord in cell.connections.items()
            }
