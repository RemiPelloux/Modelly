"""Neighbourhood lookup and caching, the graph side of a :class:`Cell`."""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

from modelly._native.loops import neighborhood
from modelly.space.cells.collection import CellCollection

if TYPE_CHECKING:
    from modelly.core.agent import Agent
    from modelly.space.cells.agents import CellAgent
    from modelly.space.cells.cell import Cell, Coordinate

MIN_NEIGHBORHOOD_RADIUS = 1


class CellNeighborhood:
    """``neighborhood``, ``get_neighborhood`` and their per-cell cache.

    A slotted base of :class:`Cell`: the attributes live in ``Cell.__slots__``.
    """

    __slots__ = ()

    _agents: list[CellAgent]
    _neighborhood_cache: dict[tuple[int, bool], CellCollection[Cell]]
    connections: dict[Coordinate, Cell]
    random: Random | None

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

        Cells land in the dict in BFS discovery order, which callers rely on
        for reproducible draws (see ``modelly._native.loops.neighborhood``).
        """
        return neighborhood(self, radius)

    def _clear_cache(self):
        """Drop this cell's cached neighborhoods."""
        self._neighborhood_cache.clear()
