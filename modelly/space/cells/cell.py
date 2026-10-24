"""Cells are positions in space that can have properties and contain agents.

A cell represents a location that can:
- Have properties (like temperature or resources)
- Track and limit the agents it contains
- Connect to neighboring cells
- Provide neighborhood information

Cells form the foundation of the cell space system, enabling rich spatial
environments where both location properties and agent behaviors matter. They're
useful for modeling things like varying terrain, infrastructure capacity, or
environmental conditions.
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

import numpy as np

from modelly.core.exceptions import (
    AgentMissingException,
    CellFullException,
    ConnectionMissingException,
)
from modelly.space.cells.agents import CellAgent
from modelly.space.cells.collection import CellCollection

if TYPE_CHECKING:
    from modelly.core.agent import Agent

Coordinate = tuple[int, ...]
MIN_NEIGHBORHOOD_RADIUS = 1


class Cell:
    """The cell represents a position in a discrete space.

    Attributes:
        coordinate (Coordinate) : the logical position(or index) of the cell in the discrete space
        position (np.ndarray | None): the physical position of the cell in the discrete space
        agents (List[Agent]): the agents occupying the cell
        capacity (int): the maximum number of agents that can simultaneously occupy the cell
        random (Random): the random number generator

    Notes:
        Neighborhoods are cached per cell, keyed on ``(radius, include_center)``.
        The cache belongs to the cell (not to the class), so discarding a space
        frees its cells, and changing one cell's connections only invalidates
        that cell's own neighborhoods.
    """

    __slots__ = [
        "_agents",
        "_empties_index",
        "_empty",
        "_neighborhood_cache",
        "_position",  # physical position
        "capacity",
        "connections",
        "coordinate",  # Logical index
        "index",  # row in CellIndex, -1 until a CellIndex is built
        "properties",
        "random",
    ]

    @property
    def empty(self) -> bool:  # noqa: D102
        return self._empty

    @empty.setter
    def empty(self, value: bool) -> None:
        self._empty = value
        index = self._empties_index
        if index is not None:
            index.set_empty(self, value)

    @property
    def position(self) -> np.ndarray:
        """Get the physical position of the cell.

        Returns:
            np.ndarray: Physical position of the cell
        """
        if self._position is not None:
            return self._position
        # Default for implicit grids
        return np.asarray(self.coordinate, dtype=float)

    @position.setter
    def position(self, value: np.ndarray | None) -> None:
        self._position = value

    def __init__(
        self,
        coordinate: Coordinate,
        position: np.ndarray | None = None,
        capacity: int | None = None,
        random: Random | None = None,
    ) -> None:
        """Initialise the cell.

        Args:
            coordinate: coordinates of the cell
            position: physical coordinates of the cell
            capacity (int) : the capacity of the cell. If None, the capacity is infinite
            random (Random) : the random number generator to use

        """
        super().__init__()
        self.coordinate = coordinate  # Logical index
        self.index = -1  # row in CellIndex, see modelly.space.cells.index
        self._position = position  # Physical position
        self.connections: dict[Coordinate, Cell] = {}
        self._agents: list[CellAgent] = []
        self._empty: bool = True  # a freshly created cell holds no agents
        self.capacity: int | None = capacity
        self.properties: dict[
            Coordinate, object
        ] = {}  # fixme still used by voronoi mesh
        self.random = random
        self._neighborhood_cache: dict[tuple[int, bool], CellCollection[Cell]] = {}
        # Set by the space's empty-cell index once it is built (see DiscreteSpace).
        self._empties_index = None

    def connect(self, other: Cell, key: Coordinate | None = None) -> None:
        """Connects this cell to another cell.

        Args:
            other (Cell): other cell to connect to
            key (Tuple[int, ...]): key for the connection. Should resemble a relative coordinate

        """
        if key is None:
            key = other.coordinate
        self._clear_cache()
        self.connections[key] = other

    def disconnect(self, other: Cell) -> None:
        """Disconnects this cell from another cell.

        Args:
            other (Cell): other cell to remove from connections

        """
        keys_to_remove = [k for k, v in self.connections.items() if v == other]

        if not keys_to_remove:
            raise ConnectionMissingException(self, other)

        for key in keys_to_remove:
            del self.connections[key]
        self._clear_cache()

    def add_agent(self, agent: CellAgent) -> None:
        """Adds an agent to the cell.

        Args:
            agent (CellAgent): agent to add to this Cell

        """
        occupants = self._agents
        limit = self.capacity
        if limit is not None and len(occupants) >= limit:
            raise CellFullException(self.coordinate)

        occupants.append(agent)
        # ``empty`` may be backed by a property layer; only write it on a transition.
        if len(occupants) == 1:
            self.empty = False

    def remove_agent(self, agent: CellAgent) -> None:
        """Removes an agent from the cell.

        Args:
            agent (CellAgent): agent to remove from this cell

        """
        try:
            self._agents.remove(agent)
        except ValueError as e:
            raise AgentMissingException(agent, self.coordinate) from e

        if not self._agents:
            self.empty = True

    @property
    def is_empty(self) -> bool:
        """Returns a bool of the contents of a cell."""
        return not self._agents

    @property
    def is_full(self) -> bool:
        """Returns a bool of the contents of a cell."""
        limit = self.capacity
        return limit is not None and len(self._agents) >= limit

    @property
    def agents(self) -> list[CellAgent]:
        """Returns a list of the agents occupying the cell."""
        return self._agents.copy()

    def __repr__(self):  # noqa
        return f"Cell({self.coordinate}, {self.agents})"

    @property
    def neighborhood(self) -> CellCollection[Cell]:
        """Returns the direct neighborhood of the cell.

        This is equivalent to cell.get_neighborhood(radius=1)

        """
        return self.get_neighborhood()

    def get_neighborhood(
        self, radius: int = 1, include_center: bool = False
    ) -> CellCollection[Cell]:
        """Returns a CellCollection of all neighboring cells for the given radius.

        For getting the direct neighborhood (i.e., radius=1) you can also use
        the `neighborhood` property.

        Args:
            radius (int): the radius of the neighborhood
            include_center (bool): include the center of the neighborhood

        Returns:
            a CellCollection of all neighboring cells

        """
        key = (radius, include_center)
        cache = self._neighborhood_cache
        try:
            return cache[key]
        except KeyError:
            pass
        # Plain CellCollection(...): calling the subscripted alias CellCollection[Cell]
        # goes through typing's __call__ and costs more than building the collection.
        collection = CellCollection(
            self._neighborhood(radius=radius, include_center=include_center),
            random=self.random,
        )
        cache[key] = collection
        return collection

    def _neighborhood(
        self, radius: int = 1, include_center: bool = False
    ) -> dict[Cell, list[Agent]]:
        """Return cells within given radius using iterative BFS.

        Note: This implementation uses iterative breadth-first search instead
        of recursion to avoid RecursionError on large radius values.
        """
        if radius < MIN_NEIGHBORHOOD_RADIUS:
            raise ValueError(f"radius must be at least {MIN_NEIGHBORHOOD_RADIUS}")

        # Fast path for radius=1 (most common case) - avoid BFS overhead
        if radius == 1:
            neighborhood = {
                neighbor: neighbor._agents for neighbor in self.connections.values()
            }
            if include_center:
                neighborhood[self] = self._agents
            return neighborhood

        neighborhood = self._bfs_neighborhood(radius)

        if include_center:
            neighborhood[self] = self._agents
        else:
            neighborhood.pop(self, None)

        return neighborhood

    def _bfs_neighborhood(self, radius: int) -> dict[Cell, list[Agent]]:
        """Collect every cell within ``radius`` hops (excluding self) by BFS.

        The result dict doubles as the visited set: self is seeded into it so it
        is never re-entered, then dropped at the end. Cells land in the dict in
        BFS discovery order, which callers rely on for reproducible draws.
        """
        reached: dict[Cell, list[Agent]] = {self: self._agents}
        frontier: list[Cell] = []
        for neighbor in self.connections.values():
            if neighbor not in reached:
                reached[neighbor] = neighbor._agents
                frontier.append(neighbor)

        for _ in range(radius - 1):
            if not frontier:
                break
            next_frontier: list[Cell] = []
            grow = next_frontier.append
            for cell in frontier:
                for neighbor in cell.connections.values():
                    if neighbor not in reached:
                        reached[neighbor] = neighbor._agents
                        grow(neighbor)
            frontier = next_frontier

        del reached[self]
        return reached

    def __getstate__(self):
        """Return state of the Cell.

        Neighbors are replaced with their coordinates to avoid deep recursion
        while preserving the connection keys. The neighborhood cache is dropped;
        it is rebuilt lazily after unpickling.
        """
        state = super().__getstate__()
        slots = state[1]
        slots["connections"] = {
            key: neighbor.coordinate for key, neighbor in self.connections.items()
        }
        slots["_neighborhood_cache"] = {}
        slots["_empties_index"] = None
        return state

    def _clear_cache(self):
        """Drop this cell's cached neighborhoods."""
        self._neighborhood_cache.clear()
