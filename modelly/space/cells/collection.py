"""Collection class for managing and querying groups of cells.

The CellCollection class provides a consistent interface for operating on multiple
cells, supporting:
- Filtering and selecting cells based on conditions
- Random cell and agent selection
- Access to contained agents
- Group operations

This is useful for implementing area effects, zones, or any operation that needs
to work with multiple cells as a unit. The collection handles efficient iteration
and agent access across cells. The class is used throughout the cell space
implementation to represent neighborhoods, selections, and other cell groupings.
"""

from __future__ import annotations

import itertools
import warnings
from collections.abc import Callable, Iterable, Mapping
from functools import cached_property
from random import Random
from typing import TYPE_CHECKING, TypeVar

from modelly.core.agentset._utils import _INF, _validate_at_most

if TYPE_CHECKING:
    from modelly.space.cells.agents import CellAgent
    from modelly.space.cells.cell import Cell

T = TypeVar("T", bound="Cell")

RAISES = object()


def _derived_random(cells: Mapping[Cell, list[CellAgent]]) -> Random | None:
    """The generator of the first cell that has one, else the first agent's model's."""
    for cell, agents in cells.items():
        if cell.random is not None:
            return cell.random
        if agents:
            return agents[0].model.random
    return None


class CellCollection[T: Cell]:
    """An immutable collection of cells.

    Attributes:
        cells (List[Cell]): The list of cells this collection represents
        agents (List[CellAgent]) : List of agents occupying the cells in this collection
        random (Random) : The random number generator

    Notes:
        With `random=None` the collection takes the generator of its first cell that has one,
        else the model generator of its first agent. A `UserWarning` is issued only when there
        is neither; pass `random=self.random` from a `Model` or `Agent` to avoid it.


    """

    def __init__(
        self,
        cells: Mapping[T, list[CellAgent]] | Iterable[T],
        random: Random | None = None,
    ) -> None:
        """Initialize a CellCollection.

        Args:
            cells: cells to add to the collection
            random: a seeded random number generator; None takes the cells' or their
                agents' model generator.
        """
        if isinstance(cells, dict):
            self._cells = cells
        else:
            self._cells = {cell: cell._agents for cell in cells}

        # Get capacity from first cell if collection is not empty
        self._capacity: int | None = (
            next(iter(self._cells.keys())).capacity if self._cells else None
        )

        if random is None:
            random = _derived_random(self._cells)
        if random is None:
            warnings.warn(
                "Random number generator not specified, this can make models non-reproducible. Please pass a random number generator explicitly",
                UserWarning,
                stacklevel=2,
            )
            random = Random()  # noqa: MDL001 (no cell or agent has a seeded generator)
        self.random = random

    def __iter__(self):  # noqa
        return iter(self._cells)

    def __getitem__(self, key: T) -> Iterable[CellAgent]:  # noqa
        return self._cells[key]

    # @cached_property
    def __len__(self) -> int:  # noqa
        return len(self._cells)

    def __repr__(self):  # noqa
        return f"CellCollection({self._cells})"

    @cached_property
    def cells(self) -> list[T]:  # noqa
        return list(self._cells.keys())

    @property
    def agents(self) -> Iterable[CellAgent]:  # noqa
        return itertools.chain.from_iterable(self._cells.values())

    @property
    def empties(self) -> CellCollection[T]:
        """The cells of this collection that hold no agent, as a new collection.

        Reads the live occupancy lists directly, so it costs one truth test per
        cell rather than a property call per cell.
        """
        return CellCollection(
            {cell: agents for cell, agents in self._cells.items() if not agents},
            random=self.random,
        )

    def select_random_cell(self, default=RAISES) -> T | None:
        """Select a random cell from the collection.

        Args:
            default: Value to return if the collection is empty.
                     If not provided, raises LookupError.

        Returns:
            T: A random cell, or the default value if provided and collection is empty.

        Raises:
            LookupError: If collection is empty and no default is provided.
        """
        if not self._cells:
            if default is RAISES:
                raise LookupError("Cannot select random cell from empty collection")
            return default

        return self.random.choice(self.cells)

    def select_random_agent(self, default=RAISES) -> CellAgent | None:
        """Select a random agent from the collection.

        Args:
            default: Value to return if the collection is empty.
                     If not provided, raises LookupError.

        Returns:
            CellAgent: A random agent, or the default value if provided and collection is empty.

        Raises:
            LookupError: If collection is empty and no default is provided.
        """
        agents = list(self.agents)

        if not agents:
            if default is RAISES:
                raise LookupError("Cannot select random agent from empty collection")
            return default

        return self.random.choice(agents)

    def select(
        self,
        filter_func: Callable[[T], bool] | None = None,
        at_most: int | float = float("inf"),
    ):
        """Select cells based on filter function.

        Args:
            filter_func: filter function
            at_most: The maximum amount of cells to select. Defaults to infinity.
              - If an integer, at most the first number of matching cells is selected.
              - If a float between 0 and 1, at most that fraction of original number of cells

        Returns:
            CellCollection

        Raises:
            TypeError: If at_most is not an integer or float, or is a boolean.
            ValueError: If at_most is a negative integer, or a float not in the range (0.0, 1.0].

        """
        if at_most == _INF:
            if filter_func is None:
                return self
            # One pass straight into the new collection's mapping.
            kept = {cell: cell._agents for cell in self._cells if filter_func(cell)}
            return CellCollection(kept, random=self.random)

        limit = _validate_at_most(at_most, len(self._cells))
        matches = (
            iter(self._cells)
            if filter_func is None
            else (cell for cell in self._cells if filter_func(cell))
        )
        # Stop filtering as soon as ``limit`` cells matched.
        kept = {cell: cell._agents for cell in itertools.islice(matches, limit)}
        return CellCollection(kept, random=self.random)
