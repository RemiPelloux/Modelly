"""SQLDataRecorder: snapshots stored as rows of a SQLite database."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any

import numpy as np

from modelly._optional import LazyModule
from modelly.data.recorders.base import BaseDataRecorder

if TYPE_CHECKING:
    import pandas as pd

    from modelly.data.recorders.config import DatasetConfig
else:
    pd = LazyModule("pandas")

# Value types that pandas' to_sql hands to sqlite3 unchanged (bar NaN, which
# SQLite stores as NULL just as pandas' None), and array kinds made only of them.
_PLAIN_TYPES = frozenset({int, float, str, bool, type(None)})
_NUMERIC_KINDS = "biuf"


def _quoted(name: str) -> str:
    """A SQLite identifier, quoted as pandas quotes it."""
    return '"' + name.replace('"', '""') + '"'


def _insert(conn: sqlite3.Connection, table: str, names: list[str], rows: list) -> None:
    """Append ``rows`` in one committed transaction, as ``DataFrame.to_sql`` does."""
    columns = ",".join(map(_quoted, names))
    marks = ",".join("?" * len(names))
    statement = f"INSERT INTO {_quoted(table)} ({columns}) VALUES ({marks})"  # noqa: S608
    with conn:
        try:
            conn.executemany(statement, rows)
        except sqlite3.Error as exc:
            raise pd.errors.DatabaseError("Execution failed") from exc


def _append_dicts(conn: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    """Append dict rows: directly when they share their keys and hold plain values.

    pandas would turn such rows into the same values (an int in a float column
    becomes a float, which the REAL column does anyway); anything else still
    goes through ``DataFrame.to_sql``.
    """
    names = list(rows[0])
    plain = (
        all(type(name) is str for name in names)
        and all(list(row) == names for row in rows)
        and _PLAIN_TYPES.issuperset(type(v) for row in rows for v in row.values())
    )
    if plain:
        _insert(conn, table, names, [tuple(row.values()) for row in rows])
    else:
        pd.DataFrame(rows).to_sql(table, conn, if_exists="append", index=False)


class SQLDataRecorder(BaseDataRecorder):
    """Store collected data in SQLite database."""

    def __init__(
        self,
        model,
        config: dict[str, DatasetConfig | dict[str, Any]] | None = None,
        db_path: str = ":memory:",
    ):
        """Initialize SQL storage backend."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.metadata: dict[str, dict] = {}
        super().__init__(model, config)

    def _initialize_dataset_storage(self, dataset_name: str, dataset: Any) -> None:
        """Initialize SQL table metadata."""
        self.metadata[dataset_name] = {"table_created": False, "columns": []}

    def _store_dataset_snapshot(
        self,
        dataset_name: str,
        time: int | float,
        data: Any,
        is_overwrite: bool = False,
    ) -> None:
        """Store data snapshot in SQL."""
        # handle overwrite
        if is_overwrite and self.metadata[dataset_name]["table_created"]:
            self.conn.execute(f'DELETE FROM "{dataset_name}" WHERE time = ?', (time,))  # noqa: S608

        match data:
            case np.ndarray() if data.size > 0:
                self._store_numpy_data(dataset_name, time, data)
            case list() if data:
                self._store_list_data(dataset_name, time, data)
            case dict():
                self._store_dict_data(dataset_name, time, data)
            case _:
                pass

    def _store_numpy_data(self, dataset_name: str, time: int | float, data: np.ndarray):
        """Store numpy array as SQL records."""
        dataset = self.registry.datasets[dataset_name]
        columns = [col for col in dataset._attributes if col != "time"]

        # Check for IDs
        if dataset is not None:
            ids = dataset.agent_ids
            ids_col = ids.reshape(-1, 1)
            data = np.hstack([ids_col, data])
            columns = ["agent_id", *columns]

        if not self.metadata[dataset_name]["table_created"]:
            self._create_numpy_table(dataset_name, columns)

        if data.dtype.kind in _NUMERIC_KINDS and type(time) in _PLAIN_TYPES:
            rows = [(*row, time) for row in data.tolist()]
            _insert(self.conn, dataset_name, [*columns, "time"], rows)
            return
        df = pd.DataFrame(data, columns=columns)
        df["time"] = time
        df.to_sql(dataset_name, self.conn, if_exists="append", index=False)

    def _create_numpy_table(self, dataset_name: str, columns: list[str]) -> None:
        """Create the table of a NumPy dataset; agent_id is an integer column."""
        # agent_id is an integer column, as in the other recorders' frames
        col_defs = ", ".join(
            f'"{col}" {"INTEGER" if col == "agent_id" else "REAL"}' for col in columns
        )
        self.conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{dataset_name}" (time REAL, {col_defs})'
        )
        self.metadata[dataset_name]["table_created"] = True
        self.metadata[dataset_name]["columns"] = columns

    def _store_list_data(self, dataset_name: str, time: int | float, data: list[dict]):
        """Store list of dicts as SQL records."""
        if not self.metadata[dataset_name]["table_created"]:
            columns = [k for k in data[0] if k != "time"]
            col_defs = ", ".join([f'"{col}" REAL' for col in columns])
            self.conn.execute(
                f'CREATE TABLE IF NOT EXISTS "{dataset_name}" (time REAL, {col_defs})'
            )
            self.metadata[dataset_name]["table_created"] = True
            self.metadata[dataset_name]["columns"] = columns

        _append_dicts(self.conn, dataset_name, [{**row, "time": time} for row in data])

    def _store_dict_data(self, dataset_name: str, time: int | float, data: dict):
        """Store single dict as SQL record."""
        if not self.metadata[dataset_name]["table_created"]:
            columns = [k for k in data if k != "time"]
            col_defs = ", ".join([f'"{col}" REAL' for col in columns])
            self.conn.execute(
                f'CREATE TABLE IF NOT EXISTS "{dataset_name}" (time REAL, {col_defs})'
            )
            self.metadata[dataset_name]["table_created"] = True
            self.metadata[dataset_name]["columns"] = columns

        _append_dicts(self.conn, dataset_name, [{**data, "time": time}])

    def get_table_dataframe(self, name: str) -> pd.DataFrame:
        """Convert stored data to pandas DataFrame."""
        if name not in self.metadata:
            raise KeyError(f"Dataset '{name}' not found")

        if not self.metadata[name]["table_created"]:
            return pd.DataFrame()

        return pd.read_sql(f'SELECT * FROM "{name}"', self.conn)  # noqa: S608

    def query(self, sql: str) -> pd.DataFrame:
        """Execute custom SQL query."""
        return pd.read_sql(sql, self.conn)

    def clear(self, dataset_name: str | None = None) -> None:
        """Clear stored data by dropping tables."""
        if dataset_name is None:
            for name in self.metadata:
                self.conn.execute(f'DROP TABLE IF EXISTS "{name}"')
                self.metadata[name]["table_created"] = False
        else:
            if dataset_name not in self.metadata:
                raise KeyError(f"Dataset '{dataset_name}' not found")

            self.conn.execute(f'DROP TABLE IF EXISTS "{dataset_name}"')
            self.metadata[dataset_name]["table_created"] = False

        self.conn.commit()

    def summary(self) -> dict[str, Any]:
        """Get collection status summary."""
        summary_data = {"datasets": len(self.metadata), "database": self.db_path}

        for name, meta in self.metadata.items():
            if meta["table_created"]:
                cursor = self.conn.execute(f'SELECT COUNT(*) FROM "{name}"')  # noqa: S608
                row_count = cursor.fetchone()[0]
            else:
                row_count = 0

            summary_data[name] = {
                "enabled": self.configs[name].enabled,
                "interval": self.configs[name].interval,
                "rows": row_count,
                "next_collection": self.configs[name]._next_collection,
            }

        return summary_data

    def __del__(self):  # pragma : no cover
        """Close database connection on cleanup."""
        if hasattr(self, "conn"):
            self.conn.close()
