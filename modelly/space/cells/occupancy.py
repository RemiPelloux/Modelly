"""Who sits in which cell, from a row column, without per-cell agent lists.

Agents that keep their cell as a ``Column`` of rows (see ``CellIndex``) move by
assigning the column; nothing else has to be updated. When a step needs to
know who shares a cell, ``Occupancy`` sorts the rows once (O(n log n)) and
answers per-cell questions from the sorted order. ``claim`` is the vectorised
form of "each claimant takes one of the members of its cell, if any is left":
it has the law of the sequential version in which the claimants act in a
uniformly random order (see docs/vectorised_phases.md).
"""

from __future__ import annotations

import numpy as np

NO_MATCH = -1
MAX_VECTOR_ROUNDS = 64
RADIX_BITS = 16
RADIX_LIMIT = 1 << RADIX_BITS
RADIX_MASK = RADIX_LIMIT - 1
TWO_PASS_LIMIT = 1 << (2 * RADIX_BITS)
OFFSET_PAD = 3  # a leading zero for cell -1, then one past the last cell, then its end


def _stable_order(rows: np.ndarray) -> np.ndarray:
    """``np.argsort(rows, kind="stable")``, through numpy's radix sort when it can.

    Non-negative integer keys below 2**16 sort as uint16 (radix sort); below
    2**32 as two stable uint16 passes, low half then high half (LSD radix).
    Both give the one stable permutation, so the result is identical.
    """
    if not _within(rows, TWO_PASS_LIMIT) or rows.shape[0] == 0:
        return np.argsort(rows, kind="stable")
    if int(rows.max()) < RADIX_LIMIT:
        return np.argsort(rows.astype(np.uint16), kind="stable")
    first = np.argsort((rows & RADIX_MASK).astype(np.uint16), kind="stable")
    second = np.argsort((rows[first] >> RADIX_BITS).astype(np.uint16), kind="stable")
    return first[second]


class Occupancy:
    """The agents of a table grouped by cell row, rebuilt from the row column."""

    def __init__(self, rows: np.ndarray, n_cells: int) -> None:
        """Sort the agents (their table indices) by the cell row they occupy."""
        self.rows = np.asarray(rows)
        self.n_cells = n_cells
        self.order = _stable_order(self.rows)
        self.sorted_rows = self.rows[self.order]
        self._offsets = _cell_offsets(self.rows)

    def counts(self) -> np.ndarray:
        """How many agents sit in each cell."""
        return np.bincount(self.rows, minlength=self.n_cells)

    def bounds(self, cells: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """The ``[start, end)`` slice of ``order`` holding the members of each cell."""
        cells = np.asarray(cells)
        offsets = self._offsets
        if offsets is not None and np.can_cast(cells.dtype, np.intp):
            at = np.clip(cells.astype(np.intp), -1, offsets.shape[0] - OFFSET_PAD)
            at += 1
            return offsets[at], offsets[at + 1]
        start = np.searchsorted(self.sorted_rows, cells, side="left")
        end = np.searchsorted(self.sorted_rows, cells, side="right")
        return start, end

    def members(self, cell: int) -> np.ndarray:
        """The table indices of the agents in ``cell``."""
        start, end = self.bounds(np.array([cell]))
        return self.order[start[0] : end[0]]

    def random_member(self, cells: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        """One uniformly chosen member of each cell in ``cells``, or ``NO_MATCH`` if empty."""
        start, end = self.bounds(cells)
        size = end - start
        pick = start + (rng.random(cells.shape[0]) * size).astype(np.intp)
        chosen = self.order[np.minimum(pick, max(self.order.shape[0] - 1, 0))]
        return np.where(size > 0, chosen, NO_MATCH)


def _cell_offsets(rows: np.ndarray) -> np.ndarray | None:
    """Prefix sums of the cell counts, padded so any integer cell can index them.

    ``offsets[c + 1]`` and ``offsets[c + 2]`` are the ``[start, end)`` of cell
    ``c`` for ``-1 <= c <= max(rows) + 1``; cells outside that range clip to the
    ends, where the slice is empty, as ``searchsorted`` finds. ``None`` when the
    rows are not non-negative integers (then ``bounds`` searches).
    """
    if not _within(rows, TWO_PASS_LIMIT):
        return None
    counts = np.bincount(rows) if rows.shape[0] else np.zeros(0, dtype=np.intp)
    offsets = np.zeros(counts.shape[0] + OFFSET_PAD, dtype=np.intp)
    np.cumsum(counts, out=offsets[2 : counts.shape[0] + 2])
    offsets[counts.shape[0] + 2 :] = rows.shape[0]
    return offsets


def _within(keys: np.ndarray, limit: int) -> bool:
    """Whether ``keys`` are integers in ``[0, limit)`` (an empty array counts)."""
    if keys.dtype.kind not in "iu" or keys.ndim != 1:
        return False
    return keys.shape[0] == 0 or (int(keys.min()) >= 0 and int(keys.max()) < limit)


def claim(
    occupancy: Occupancy, cells: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """For each claimant, one distinct member of its cell, or ``NO_MATCH``.

    ``cells[k]`` is the cell of claimant ``k``. The matching has the law of the
    sequential rule "claimants act in a uniformly random order and each takes a
    uniformly random member of its cell not yet taken": every cell ends up with
    min(claimants, members) matches, a uniform random subset of its members is
    taken and a uniform random subset of its claimants is served. Each round,
    every unserved claimant draws a member of its cell; draws of already taken
    members are rejected, collisions go to a random priority, and the losers
    draw again while their cell still has a free member.
    """
    cells = np.asarray(cells)
    taken = np.zeros(occupancy.order.shape[0], dtype=bool)
    result = np.full(cells.shape[0], NO_MATCH, dtype=np.intp)
    priority = rng.permutation(cells.shape[0])
    free = occupancy.counts()
    active = np.flatnonzero(free[cells] > 0)
    rounds = 0
    while active.shape[0] and rounds < MAX_VECTOR_ROUNDS:
        rounds += 1
        active = _claim_round(
            occupancy, cells, rng, taken, result, priority, free, active
        )
    if active.shape[0]:
        _claim_sequentially(
            occupancy, cells, rng, taken, result, priority, free, active
        )
    return result


def _claim_round(occupancy, cells, rng, taken, result, priority, free, active):
    """One vectorised round; returns the claimants still to serve."""
    picks = occupancy.random_member(cells[active], rng)
    valid = ~taken[picks]
    candidates, picks = active[valid], picks[valid]
    order = np.argsort(priority[candidates], kind="stable")
    candidates, picks = candidates[order], picks[order]
    won, first = np.unique(picks, return_index=True)
    winners = candidates[first]
    result[winners] = won
    taken[won] = True
    np.subtract.at(free, cells[winners], 1)
    unserved = active[result[active] == NO_MATCH]
    return unserved[free[cells[unserved]] > 0]


def _claim_sequentially(occupancy, cells, rng, taken, result, priority, free, active):
    """Serve the remaining claimants one by one, in priority order (the exact rule)."""
    for k in active[np.argsort(priority[active], kind="stable")]:
        if free[cells[k]] <= 0:
            continue
        members = occupancy.members(cells[k])
        candidates = members[~taken[members]]
        chosen = candidates[int(rng.integers(candidates.shape[0]))]
        result[k] = chosen
        taken[chosen] = True
        free[cells[k]] -= 1
