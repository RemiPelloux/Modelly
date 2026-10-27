"""``CohortTable`` on a device: binomial thinning, splits and merges as array programs.

:class:`DeviceCohortTable` has the operations of
:class:`~modelly.batch.cohorts.CohortTable` (``add``, ``thin``, ``draw``,
``split``, ``compact``, ``merge``, ``total``, ``totals_by``) with the columns
on a backend and the binomial draws from a
:class:`~modelly.gpu.streams.PhiloxStream`, so the same seed gives the same
counts on numpy, CuPy and JAX. Updates are functional: ``table["age"] = ...``
replaces the column, and ``table["stage"][rows] = x`` (which works on the host
table) is written ``table.set_where("stage", mask, x)``.

The law of every operation is the host table's (``docs/vectorised_phases.md``,
cohort compression); the numbers differ from the host table's, which draws
from ``model.rng``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from modelly.batch.cohorts import COUNT

if TYPE_CHECKING:
    from modelly.batch.cohorts import CohortTable
    from modelly.gpu.backend import Backend
    from modelly.gpu.streams import PhiloxStream


class DeviceCohortTable:
    """Rows of (state columns, count) on a device.

    Args:
        stream: the PhiloxStream the binomial draws come from; its backend holds the rows.
        columns: state column names and their dtypes.
    """

    def __init__(self, stream: PhiloxStream, **columns: Any) -> None:
        """An empty table with an integer ``count`` and the given state columns."""
        if COUNT in columns:
            raise ValueError(f"'{COUNT}' is reserved for the cohort sizes")
        self.stream = stream
        xp = stream.backend.xp
        dtypes = {COUNT: stream.backend.int_dtype} | columns
        self._data = {name: xp.zeros(0, dtype=dtype) for name, dtype in dtypes.items()}

    @classmethod
    def from_table(cls, table: CohortTable, stream: PhiloxStream) -> DeviceCohortTable:
        """A copy of the live rows of a host ``CohortTable``."""
        states = {name: table[name].dtype for name in table.columns if name != COUNT}
        device = cls(stream, **states)
        device.add(table[COUNT], **{name: table[name] for name in states})
        return device

    @property
    def backend(self) -> Backend:
        """The backend the rows live on."""
        return self.stream.backend

    @property
    def columns(self) -> list[str]:
        """``count`` then the state columns."""
        return list(self._data)

    def __len__(self) -> int:
        """Number of rows (cohorts), not individuals."""
        return int(self._data[COUNT].shape[0])

    def __getitem__(self, name: str) -> Any:
        """Column ``name`` (a device array)."""
        return self._data[name]

    def __setitem__(self, name: str, values: Any) -> None:
        """Replace column ``name`` for every row (scalars broadcast)."""
        xp = self.backend.xp
        old = self._data[name]
        self._data[name] = xp.broadcast_to(
            xp.asarray(values, dtype=old.dtype), old.shape
        )

    def set_where(self, name: str, mask: Any, value: Any) -> None:
        """``column[mask] = value``, functionally."""
        self[name] = self.backend.xp.where(mask, value, self._data[name])

    def total(self, where: Any = None) -> int:
        """Individuals in the table, or in the rows selected by the mask ``where``."""
        counts = self._data[COUNT]
        if where is not None:
            counts = self.backend.xp.where(where, counts, 0)
        return int(counts.sum())

    def totals_by(self, column: str, minlength: int = 0) -> Any:
        """Individuals per value of an integer state column (a device array)."""
        index = self._data[column].astype(self.backend.int_dtype)
        return self.backend.segment_add(index, self._data[COUNT], minlength)

    def add(self, count: Any, **values: Any) -> Any:
        """Append cohorts (scalars or equal-length arrays); returns their row indices."""
        xp = self.backend.xp
        counts = xp.atleast_1d(xp.asarray(count, dtype=self._data[COUNT].dtype))
        k, first = int(counts.shape[0]), len(self)
        unknown = set(values) - set(self._data)
        if unknown:
            raise KeyError(f"unknown columns {sorted(unknown)}")
        for name, column in self._data.items():
            new = counts if name == COUNT else values.get(name, 0)
            new = xp.broadcast_to(xp.asarray(new, dtype=column.dtype), (k,))
            self._data[name] = xp.concatenate([column, new])
        return xp.arange(first, first + k)

    def thin(self, survival: Any) -> Any:
        """Each count becomes Binomial(count, survival); returns the new counts."""
        self._data[COUNT] = self.stream.binomial(self._data[COUNT], survival)
        return self._data[COUNT]

    def draw(self, p: Any, where: Any = None) -> Any:
        """Binomial(count, p) events per row (or per selected row); counts unchanged."""
        counts = self._data[COUNT]
        if where is not None:
            counts = counts[self.backend.xp.nonzero(where)[0]]
        return self.stream.binomial(counts, p)

    def split(self, p: Any, where: Any = None, **changes: Any) -> Any:
        """Move Binomial(count, p) individuals of each selected row to a new row.

        The new rows copy their source row's state, then apply ``changes``.
        Returns the new rows' indices.
        """
        xp = self.backend.xp
        rows = xp.arange(len(self)) if where is None else xp.nonzero(where)[0]
        counts = self._data[COUNT]
        moving = self.stream.binomial(counts[rows], p)
        self._data[COUNT] = self.backend.put(counts, rows, counts[rows] - moving)
        state = {n: column[rows] for n, column in self._data.items() if n != COUNT}
        return self.add(moving, **(state | changes))

    def compact(self) -> int:
        """Drop the empty cohorts, keeping row order; returns how many were dropped."""
        keep = self._data[COUNT] > 0
        kept = int(keep.sum())
        dropped = len(self) - kept
        if dropped:
            self._data = {name: column[keep] for name, column in self._data.items()}
        return dropped

    def merge(self) -> int:
        """Combine rows with identical state, summing counts; sorted by state, no empties."""
        self.compact()
        names = [name for name in self._data if name != COUNT]
        if not names or len(self) == 0:
            return 0
        backend, xp = self.backend, self.backend.xp
        order = xp.arange(len(self))
        for name in reversed(names):  # least significant column first: lexicographic
            order = order[backend.argsort_stable(self._data[name][order])]
        data = {name: column[order] for name, column in self._data.items()}
        change = xp.zeros(len(self) - 1, dtype=bool)
        for name in names:
            change = change | (data[name][1:] != data[name][:-1])
        first = xp.concatenate([xp.ones(1, dtype=bool), change])
        group = xp.cumsum(first.astype(backend.int_dtype)) - 1
        removed = len(self) - int(first.sum())
        heads = xp.nonzero(first)[0]
        sums = backend.segment_add(group, data[COUNT], int(heads.shape[0]))
        self._data = {n: sums if n == COUNT else data[n][heads] for n in data}
        return removed

    def to_dataframe(self) -> pd.DataFrame:
        """A host copy of the rows."""
        return pd.DataFrame(
            {name: self.backend.to_numpy(column) for name, column in self._data.items()}
        )

    def __repr__(self) -> str:
        """Rows, individuals and columns."""
        return (
            f"<DeviceCohortTable {len(self)} cohorts, {self.total():,} individuals, "
            f"columns={self.columns} on {self.backend.name}>"
        )
