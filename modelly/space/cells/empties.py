"""The index of the empty cells of a discrete space."""

from __future__ import annotations

from collections.abc import Sequence
from random import Random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modelly.space.cells.cell import Cell


class _EmptiesIndex:
    """The empty cells of a space, with O(1) add, discard and random pick.

    A list gives the random pick and a dict maps each cell to its list slot, so
    a discard swaps the last cell into the freed slot instead of shifting. Once
    built, every cell of the space points at the index and ``cell.empty``
    keeps it current.
    """

    __slots__ = ("_cells", "_slots", "enabled")

    def __init__(self) -> None:
        self._cells: list[Cell] = []
        self._slots: dict[Cell, int] = {}
        self.enabled = False

    def build(self, cells: Sequence[Cell]) -> None:
        """Index the empty cells among ``cells`` and start tracking transitions."""
        self._cells = [cell for cell in cells if not cell._agents]
        self._slots = {cell: i for i, cell in enumerate(self._cells)}
        for cell in cells:
            cell._empties_index = self
        self.enabled = True

    def set_empty(self, cell: Cell, is_empty: bool) -> None:
        """Record that ``cell`` became empty or occupied."""
        if is_empty:
            if cell not in self._slots:
                self._slots[cell] = len(self._cells)
                self._cells.append(cell)
            return
        slot = self._slots.pop(cell, None)
        if slot is None:
            return
        last = self._cells.pop()
        if slot < len(self._cells):
            self._cells[slot] = last
            self._slots[last] = slot

    def choice(self, random: Random) -> Cell:
        """Return a random empty cell; raises IndexError when there is none."""
        return random.choice(self._cells)

    def __len__(self) -> int:
        return len(self._cells)
