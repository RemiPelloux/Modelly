"""Counted populations: one row stands for every individual in the same state.

When individuals that share a state (stage, age, sex, patch...) also share
every probability they face, the model does not need one object per
individual. A ``CohortTable`` keeps one row per state with a ``count``, and
the per-individual draws become one binomial draw per row:

* survival with probability ``s``: ``Binomial(count, s)`` survivors (``thin``);
* a two-way outcome with probability ``p`` (sex, mating, emergence):
  ``Binomial(count, p)`` rows move to the new state (``split``);
* an event each member triggers with probability ``p``: ``Binomial(count, p)``
  events (``draw``).

Each has exactly the law of the independent per-individual draws (a sum of
``count`` independent Bernoulli(p) variables is Binomial(count, p)), so the
counts per state have the same distribution as in the individual model; see
``docs/vectorised_phases.md``. The table grows by doubling and ``compact`` /
``merge`` keep it small: it holds as many rows as there are distinct states.

    eggs = CohortTable(rng, stage=np.int8, age=np.int16)
    eggs.add(500, stage=EGG, age=0)
    eggs.thin(survival[eggs["stage"]])
    eggs["age"] += 1
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from modelly.core.storage import IN_MEMORY, InMemory, pickled, restored

COUNT = "count"
INITIAL_ROWS = 64
GROWTH_FACTOR = 2


class CohortTable:
    """Rows of (state columns, count); every operation is one numpy call per column."""

    def __init__(
        self, rng: np.random.Generator, *, storage: InMemory = IN_MEMORY, **columns: Any
    ) -> None:
        """Create an empty table with an int64 ``count`` and the given state columns.

        Args:
            rng: the model's seeded numpy generator (``model.rng``).
            storage: where the columns live (``modelly.core.storage``); a
                ``MemoryMapped`` keeps them in files, for more rows than memory.
            columns: state column names and their numpy dtypes.
        """
        if COUNT in columns:
            raise ValueError(f"'{COUNT}' is reserved for the cohort sizes")
        self.rng = rng
        self._dtypes = {COUNT: np.dtype(np.int64)} | {
            name: np.dtype(dtype) for name, dtype in columns.items()
        }
        self._storage = storage
        self._data = storage.allocate_all(self._layout(), INITIAL_ROWS)
        self._n = 0

    def _layout(self) -> dict[str, tuple[np.dtype, int]]:
        """Every column with its dtype; rows start at zero."""
        return {name: (dtype, 0) for name, dtype in self._dtypes.items()}

    def __getstate__(self) -> dict:
        """Memory-mapped columns are pickled as their rows."""
        return pickled(self.__dict__)

    def __setstate__(self, state: dict) -> None:
        """Columns come back into the table's storage (a new folder when memory-mapped)."""
        self.__dict__.update(restored(state))

    def __len__(self) -> int:
        """Number of rows (cohorts), not individuals."""
        return self._n

    def __getitem__(self, name: str) -> np.ndarray:
        """A writable view of column ``name`` over the live rows."""
        return self._data[name][: self._n]

    def __setitem__(self, name: str, values: Any) -> None:
        """Write column ``name`` for every live row, in place."""
        self._data[name][: self._n] = values

    @property
    def columns(self) -> list[str]:
        """``count`` then the state columns."""
        return list(self._data)

    def total(self, where: np.ndarray | None = None) -> int:
        """Individuals in the table, or in the rows selected by the mask ``where``."""
        counts = self["count"]
        return int(counts.sum() if where is None else counts[where].sum())

    def totals_by(self, column: str, minlength: int = 0) -> np.ndarray:
        """Individuals per value of an integer state column (a weighted bincount)."""
        return np.bincount(
            self[column], weights=self["count"], minlength=minlength
        ).astype(np.int64)

    def add(self, count: Any, **values: Any) -> np.ndarray:
        """Append cohorts; scalars or equal-length arrays. Returns their row indices.

        Unset state columns are zero. Cohorts of size zero are kept until
        ``compact``.
        """
        counts = np.atleast_1d(np.asarray(count, dtype=np.int64))
        k = counts.shape[0]
        for name, value in values.items():
            if name not in self._data:
                raise KeyError(f"unknown column {name!r}")
            if np.ndim(value) and np.shape(value)[0] != k:
                raise ValueError(
                    f"column {name!r} has {np.shape(value)[0]} values for {k} cohorts"
                )
        self._reserve(self._n + k)
        rows = np.arange(self._n, self._n + k)
        for name, column in self._data.items():
            column[rows] = counts if name == COUNT else values.get(name, 0)
        self._n += k
        return rows

    def thin(self, survival: Any) -> np.ndarray:
        """Each count becomes Binomial(count, survival); returns the new counts."""
        counts = self["count"]
        counts[:] = self.rng.binomial(counts, survival)
        return counts

    def draw(self, p: Any, where: np.ndarray | None = None) -> np.ndarray:
        """Binomial(count, p) events per row (or per selected row); counts are unchanged."""
        counts = self["count"] if where is None else self["count"][where]
        events: np.ndarray = self.rng.binomial(counts, p)
        return events

    def split(
        self, p: Any, where: np.ndarray | None = None, **changes: Any
    ) -> np.ndarray:
        """Move Binomial(count, p) individuals of each selected row to a new row.

        The new rows copy the state of their source row, then apply ``changes``
        (scalars or one value per selected row). The source rows keep the rest.
        Returns the new rows' indices.
        """
        rows = np.arange(self._n) if where is None else np.flatnonzero(where)
        moving = self.rng.binomial(self["count"][rows], p)
        self["count"][rows] -= moving
        state = {name: self[name][rows] for name in self._data if name != COUNT}
        return self.add(moving, **(state | changes))

    def compact(self) -> int:
        """Drop the empty cohorts, keeping row order; returns how many were dropped."""
        keep = self["count"] > 0
        kept = int(keep.sum())
        dropped = self._n - kept
        if dropped:
            for column in self._data.values():
                column[:kept] = column[: self._n][keep]
            self._n = kept
        return dropped

    def merge(self) -> int:
        """Combine rows with identical state into one, summing counts; drops empties.

        Rows come out sorted by state. Returns how many rows were removed.
        """
        self.compact()
        names = [name for name in self._data if name != COUNT]
        if not names or self._n == 0:
            return 0
        keys = np.rec.fromarrays([self[name] for name in names], names=names)
        unique, inverse = np.unique(keys, return_inverse=True)
        sums = np.bincount(inverse, weights=self["count"]).astype(np.int64)
        removed = self._n - int(unique.shape[0])
        self._n = unique.shape[0]
        self["count"] = sums
        for name in names:
            self[name] = unique[name]
        return removed

    def to_dataframe(self) -> pd.DataFrame:
        """A copy of the live rows."""
        return pd.DataFrame({name: self[name].copy() for name in self._data})

    def _reserve(self, rows: int) -> None:
        capacity = self._data[COUNT].shape[0]
        if rows <= capacity:
            return
        while capacity < rows:
            capacity *= GROWTH_FACTOR
        self._data = self._storage.grow_all(self._data, self._layout(), capacity)

    def __repr__(self) -> str:
        """Rows, individuals and columns."""
        return f"<CohortTable {self._n} cohorts, {self.total():,} individuals, columns={self.columns}>"


def from_counts(
    rng: np.random.Generator, counts: Mapping[tuple[Any, ...], int], **columns: Any
) -> CohortTable:
    """A table from ``{(state values...): count}``, the state in ``columns`` order."""
    table = CohortTable(rng, **columns)
    if counts:
        states = np.array(list(counts.keys()))
        table.add(
            list(counts.values()),
            **{name: states[:, i] for i, name in enumerate(columns)},
        )
    return table
