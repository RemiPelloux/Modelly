"""Columnar storage of the agent rows a DataCollector gathers on one step.

A collection used to be stored as one ``(time, unique_id, *values)`` tuple per
agent, built on every step and taken apart again on export. :class:`AgentRows`
keeps the ids and the reporter columns as gathered and yields the same tuples
lazily, so every reader sees the rows it always did.

:func:`records_frame` builds the export DataFrame straight from the columns
when each column holds a single kind of scalar, and otherwise falls back to
``DataFrame.from_records`` over the rows, which is what the export always did.
"""

from __future__ import annotations

import operator
from collections.abc import Iterator, Sequence
from itertools import chain, repeat
from typing import TYPE_CHECKING, Any

import numpy as np

from modelly._optional import LazyModule

if TYPE_CHECKING:
    import pandas as pd
else:
    pd = LazyModule("pandas")

INDEX = ("Step", "AgentID")

# The exact Python and numpy scalar types whose column pandas infers as one
# numpy dtype, whatever mix of them a column holds.
_KINDS: dict[type, np.dtype] = {
    int: np.dtype(np.int64),
    np.int64: np.dtype(np.int64),
    float: np.dtype(np.float64),
    np.float64: np.dtype(np.float64),
    bool: np.dtype(np.bool_),
    np.bool_: np.dtype(np.bool_),
}


class AgentRows(Sequence):
    """The rows of one collection, stored as an id list and one list per reporter."""

    __slots__ = ("_arrays", "columns", "ids", "time")

    def __init__(self, time: Any, ids: list, columns: list[list]) -> None:
        """Rows ``(time, ids[i], *(column[i] for column in columns))``."""
        self.time = time
        self.ids = ids
        self.columns = columns
        self._arrays: list[np.ndarray | None] | None = None

    def __len__(self) -> int:
        """The number of rows (agents)."""
        return len(self.ids)

    def __iter__(self) -> Iterator[tuple]:
        """The row tuples, built as they are read."""
        return zip(repeat(self.time), self.ids, *self.columns)

    def __getitem__(self, index: Any) -> Any:
        """One row tuple, or a list of them for a slice."""
        if isinstance(index, slice):
            return list(self)[index]
        return (self.time, self.ids[index], *[c[index] for c in self.columns])

    def __eq__(self, other: object) -> bool:
        """Equal to any rows, or list or tuple of rows, with the same tuples."""
        if isinstance(other, (AgentRows, list, tuple)):
            return list(self) == list(other)
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        """The list of row tuples."""
        return repr(list(self))

    def __reduce__(self) -> tuple:
        """Pickle the ids and columns, not the cached arrays."""
        return (AgentRows, (self.time, self.ids, self.columns))

    def arrays(self) -> list[np.ndarray | None]:
        """Step, id and reporter columns as numpy arrays (None where a column is mixed)."""
        if self._arrays is None:
            n = len(self.ids)
            columns = [[self.time] if n else [], self.ids, *self.columns]
            arrays = [_as_array(column) for column in columns]
            if n and arrays[0] is not None:
                arrays[0] = np.repeat(arrays[0], n)
            self._arrays = arrays
        return self._arrays


def _as_array(column: list) -> np.ndarray | None:
    """``column`` as the numpy array pandas would infer, or None if it is not one kind."""
    kinds = {_KINDS.get(kind) for kind in set(map(type, column))}
    if len(kinds) != 1 or None in kinds:
        return None
    try:
        return np.array(column, dtype=kinds.pop())
    except OverflowError:  # an int beyond int64: pandas infers another dtype
        return None


def records_frame(records: Sequence[Any], names: Sequence[str]) -> Any:
    """The ``(Step, AgentID)``-indexed DataFrame of every row in ``records``.

    Equal, dtypes included, to ``DataFrame.from_records`` over all the rows.
    """
    return _build(records, list(names))[0]


def growing_frame(cache: FrameCache | None, records: list, names: list[str]) -> Any:
    """:func:`records_frame`, extending the frame of the last call when it can.

    ``cache`` is updated in place and holds the records the frame was built
    from. When those are, by identity, the start of ``records`` and every
    column keeps its numpy dtype, only the new records are converted and
    appended; anything else is a fresh build. The result always equals a
    fresh build, and a copy is returned so the caller cannot alter the cache.
    """
    if cache is not None and cache.extends(records, names):
        done = len(cache.records)
        if done == len(records):
            return cache.frame.copy()
        new, fast = _build(records[done:], names)
        if fast and _same_dtypes(cache.frame, new):
            cache.update(records, names, pd.concat([cache.frame, new]), fast)
            return cache.frame.copy()
    frame, fast = _build(records, names)
    if cache is None:
        return frame
    cache.update(records, names, frame, fast)
    return frame.copy()


class FrameCache:
    """The records the last agent frame was built from, and that frame."""

    __slots__ = ("fast", "frame", "names", "records")

    def __init__(self) -> None:
        """Start with no frame."""
        self.records: list = []
        self.names: list[str] = []
        self.frame: Any = None
        self.fast = False

    def __reduce__(self) -> tuple:
        """A pickle or copy starts with an empty cache."""
        return (FrameCache, ())

    def extends(self, records: list, names: list[str]) -> bool:
        """Whether a fast frame was built from the first records of ``records``."""
        done = self.records
        return (
            self.fast
            and names == self.names
            and len(done) <= len(records)
            and all(map(operator.is_, done, records))
        )

    def update(self, records: list, names: list[str], frame: Any, fast: bool) -> None:
        """Remember ``frame`` as built from ``records``."""
        self.records, self.names, self.frame, self.fast = records, names, frame, fast


def _same_dtypes(frame: Any, new: Any) -> bool:
    """Whether two fast frames share every column and index level dtype."""
    levels = zip(frame.index.levels, new.index.levels)
    return list(frame.dtypes) == list(new.dtypes) and all(
        a.dtype == b.dtype for a, b in levels
    )


def _build(records: Sequence[Any], names: list[str]) -> tuple[Any, bool]:
    """The frame of ``records``, and whether it was built from numpy columns."""
    columns = [*INDEX, *names]
    arrays = _joined_arrays(records, len(columns))
    if arrays is None or not names or len(set(columns)) != len(columns):
        rows = list(chain.from_iterable(records))
        frame = pd.DataFrame.from_records(rows, columns=columns, index=list(INDEX))
        return frame, False
    index = pd.MultiIndex.from_arrays(arrays[:2], names=list(INDEX))
    frame = pd.DataFrame(dict(zip(names, arrays[2:])), index=index, columns=names)
    return frame, True


def _joined_arrays(records: Sequence[Any], width: int) -> list[np.ndarray] | None:
    """Each column joined over ``records``, or None unless every column is one dtype."""
    chunks = [r.arrays() for r in records if type(r) is AgentRows and len(r)]
    if not chunks or len(chunks) != sum(1 for r in records if len(r)):
        return None
    if any(len(chunk) != width for chunk in chunks):
        return None
    joined = []
    for position in range(width):
        parts = [chunk[position] for chunk in chunks]
        if any(part is None or part.dtype != parts[0].dtype for part in parts):
            return None
        joined.append(np.concatenate(parts))
    return joined
