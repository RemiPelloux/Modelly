"""Agent columns on a device: the array side of a ``ColumnTable``, on a GPU.

A :class:`DeviceTable` holds one device array per column and a
:class:`~modelly.gpu.streams.PhiloxStream`. A step phase reads columns as
arrays and assigns new ones; assignment replaces the column (JAX arrays
cannot be written in place), so a phase is written functionally::

    people = DeviceTable.from_columns(model.columns[Person], stream)
    infected = people.state == I
    exposure = index.counts(people.row, infected)[people.row]
    catches = (people.state == S) & people.draw(escape_probability[exposure])
    people.state = xp.where(catches, I, people.state)
    people.write_to(model.columns[Person])   # back to the agents, when needed

The same code runs on numpy, CuPy and JAX; with the same seed and stream it
draws the same numbers on each. The population is fixed while the columns are
on the device: add and remove agents on the host table, then copy again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from modelly.gpu.backend import Backend

if TYPE_CHECKING:
    from modelly.core.columns import ColumnTable
    from modelly.gpu.streams import PhiloxStream

ID_COLUMN = "unique_id"


class DeviceTable:
    """Equal-length device columns and the stream their phases draw from.

    Args:
        stream: the PhiloxStream of the table; its backend holds the columns.
        columns: column names and their initial values (host or device arrays).
    """

    def __init__(self, stream: PhiloxStream, **columns: Any) -> None:
        """Copy every column to the stream's backend; they must have one length."""
        data = {
            name: stream.backend.asarray(values) for name, values in columns.items()
        }
        lengths = {int(values.shape[0]) for values in data.values()}
        if len(lengths) > 1:
            raise ValueError(f"columns have different lengths: {sorted(lengths)}")
        object.__setattr__(self, "stream", stream)
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_n", lengths.pop() if lengths else 0)

    @classmethod
    def from_columns(
        cls, table: ColumnTable, stream: PhiloxStream, names: list[str] | None = None
    ) -> DeviceTable:
        """The live rows of a host ``ColumnTable`` (every column, or ``names``)."""
        names = table.columns if names is None else names
        return cls(stream, **{name: table[name] for name in names})

    @property
    def backend(self) -> Backend:
        """The backend the columns live on."""
        return self.stream.backend

    @property
    def xp(self) -> Any:
        """The backend's array namespace."""
        return self.stream.backend.xp

    @property
    def columns(self) -> list[str]:
        """The column names."""
        return list(self._data)

    def __len__(self) -> int:
        """Return the number of rows."""
        return self._n

    def __contains__(self, name: str) -> bool:
        """Return whether ``name`` is a column."""
        return name in self._data

    def __getitem__(self, name: str) -> Any:
        """The device array of column ``name``."""
        return self._data[name]

    def __setitem__(self, name: str, values: Any) -> None:
        """Replace column ``name`` (cast to its dtype; scalars are broadcast)."""
        xp = self.xp
        old = self._data.get(name)
        dtype = None if old is None else old.dtype
        new = xp.asarray(values, dtype=dtype)
        self._data[name] = xp.broadcast_to(new, (self._n,)) if new.ndim == 0 else new
        if self._data[name].shape[0] != self._n:
            raise ValueError(f"column {name!r} needs {self._n} values")

    def __getattr__(self, name: str) -> Any:
        """``table.<column>``; only reached for names that are not attributes."""
        data = self.__dict__.get("_data")
        if data is not None and name in data:
            return data[name]
        raise AttributeError(f"{type(self).__name__} has no column {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        """``table.<column> = values`` replaces an existing column."""
        if name in self._data:
            self[name] = value
            return
        object.__setattr__(self, name, value)

    def draw(self, p: Any) -> Any:
        """One Bernoulli(p) per row, ``p`` a probability or one per row."""
        return self.stream.bernoulli(p, self._n)

    def set_where(self, name: str, mask: Any, value: Any) -> None:
        """``column[mask] = value``, functionally."""
        self[name] = self.xp.where(mask, value, self._data[name])

    def thin(self, name: str, survival: Any) -> Any:
        """Replace the counts in ``name`` by Binomial(count, survival); returns them."""
        self[name] = self.stream.binomial(self._data[name], survival)
        return self._data[name]

    def to_numpy(self, name: str) -> Any:
        """A host copy of column ``name``."""
        return self.backend.to_numpy(self._data[name])

    def to_dataframe(self) -> pd.DataFrame:
        """A host copy of every column, indexed by ``unique_id`` when it is one."""
        frame = pd.DataFrame({name: self.to_numpy(name) for name in self._data})
        return frame.set_index(ID_COLUMN) if ID_COLUMN in frame else frame

    def write_to(self, table: ColumnTable, names: list[str] | None = None) -> None:
        """Copy columns back into the live rows of a host ``ColumnTable`` (same rows)."""
        if len(table) != self._n:
            raise ValueError(
                f"the host table has {len(table)} rows, this one {self._n}"
            )
        for name in self.columns if names is None else names:
            if name != ID_COLUMN:
                table[name][:] = self.to_numpy(name)

    def __repr__(self) -> str:
        """Rows, columns and backend."""
        return f"<DeviceTable {self._n} rows, columns={self.columns} on {self.backend.name}>"
