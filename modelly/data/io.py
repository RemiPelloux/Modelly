"""Arrow and Parquet export of a DataCollector, and SQL over the results with DuckDB.

pyarrow and duckdb are optional: ``pip install "modelly-abm[experiments]"``.
Parquet files are written atomically (a temporary file in the same folder,
then ``os.replace``), so a reader never sees half a file, on any platform.

Example:
    >>> collector.to_parquet("runs/model.parquet")  # doctest: +SKIP
    >>> query("SELECT avg(Gini) FROM model", model=collector.to_arrow())  # doctest: +SKIP
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from modelly._optional import require
from modelly.data.xarray_export import to_xarray

EXTRA = "experiments"
KINDS = ("model", "agent", "agenttype", "table")
TEMP_SUFFIX = ".tmp"


def _frame(collector: Any, kind: str, name: Any = None):
    """The pandas DataFrame of one collection, with its index as columns."""
    if kind == "model":
        return collector.get_model_vars_dataframe()
    if kind == "agent":
        return collector.get_agent_vars_dataframe().reset_index()
    if kind == "agenttype":
        if name is None:
            raise ValueError("kind='agenttype' needs name=<the agent class>")
        return collector.get_agenttype_vars_dataframe(name).reset_index()
    if kind == "table":
        if name is None:
            raise ValueError("kind='table' needs name=<the table name>")
        return collector.get_table_dataframe(name)
    raise ValueError(f"kind must be one of {', '.join(KINDS)}, got {kind!r}")


def to_arrow(collector: Any, kind: str = "model", name: Any = None):
    """One collection of ``collector`` as a ``pyarrow.Table``.

    Args:
        collector: a DataCollector.
        kind: ``"model"``, ``"agent"`` (with ``Step`` and ``AgentID`` columns),
            ``"agenttype"`` or ``"table"``.
        name: the agent class for ``"agenttype"``, the table name for ``"table"``.

    Example:
        >>> table = to_arrow(model.datacollector, "agent")  # doctest: +SKIP
    """
    pa = require("pyarrow", EXTRA)
    return pa.Table.from_pandas(_frame(collector, kind, name), preserve_index=False)


def write_parquet_atomic(table: Any, path: str | Path) -> Path:
    """Write a ``pyarrow.Table`` to ``path`` atomically; return the path.

    The table goes to a temporary file next to ``path`` first, then
    ``os.replace`` moves it into place, so a crash leaves no partial file.
    """
    parquet = require("pyarrow.parquet", EXTRA)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}{TEMP_SUFFIX}")
    try:
        parquet.write_table(table, temp)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return path


def to_parquet(
    collector: Any, path: str | Path, kind: str = "model", name: Any = None
) -> Path:
    """Write one collection of ``collector`` to a Parquet file, atomically.

    Arguments are those of :func:`to_arrow`; returns the path written.

    Example:
        >>> to_parquet(model.datacollector, "out/agents.parquet", "agent")  # doctest: +SKIP
    """
    return write_parquet_atomic(to_arrow(collector, kind, name), path)


def query(sql: str, connection: Any = None, **tables: Any):
    """Run ``sql`` with DuckDB over named tables; return a DuckDB relation.

    Each keyword names a table in the query: a ``pyarrow.Table``, a pandas
    DataFrame, or a path (or glob) of Parquet files.

    Example:
        >>> query("SELECT count(*) FROM runs", runs="out/*.parquet").fetchone()  # doctest: +SKIP
    """
    duckdb = require("duckdb", EXTRA)
    connection = duckdb.connect() if connection is None else connection
    for table_name, source in tables.items():
        _register(connection, table_name, source)
    return connection.sql(sql)


def _register(connection: Any, table_name: str, source: Any) -> None:
    """Make ``source`` queryable as ``table_name`` on ``connection``."""
    if isinstance(source, str | Path):
        pattern = Path(source).as_posix().replace("'", "''")
        connection.sql(
            f'CREATE OR REPLACE VIEW "{table_name}" AS '  # noqa: S608 (local paths)
            f"SELECT * FROM read_parquet('{pattern}', union_by_name = true)"
        )
        return
    connection.register(table_name, source)


class ArrowExportMixin:
    """``to_arrow``, ``to_parquet`` and ``to_xarray`` on the DataCollector."""

    def to_arrow(self, kind: str = "model", name: Any = None):
        """This collector's ``kind`` collection as a ``pyarrow.Table`` (see :func:`to_arrow`)."""
        return to_arrow(self, kind, name)

    def to_parquet(
        self, path: str | Path, kind: str = "model", name: Any = None
    ) -> Path:
        """Write this collector's ``kind`` collection to Parquet (see :func:`to_parquet`)."""
        return to_parquet(self, path, kind, name)

    def to_xarray(self, kind: str = "model", name: Any = None, dims: Any = None):
        """This collector's ``kind`` collection as an ``xarray.Dataset`` (see ``to_xarray``)."""
        return to_xarray(self, kind, name, dims)


def tables_of(collector: Any) -> Mapping[str, Any]:
    """Every non-empty collection of ``collector`` by name: ``model``, ``agent`` and its tables."""
    found: dict[str, Any] = {}
    if collector.model_reporters:
        found["model"] = to_arrow(collector, "model")
    if collector.agent_reporters:
        found["agent"] = to_arrow(collector, "agent")
    for table_name in collector.tables:
        found[table_name] = to_arrow(collector, "table", table_name)
    return found
