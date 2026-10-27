"""A run's outputs: the tables its DataCollector holds, written to Parquet or CSV.

Each table becomes one file named after it. Parquet is used when pyarrow is installed
and the table converts; otherwise, and for tables Parquet cannot hold, CSV (UTF-8).
"""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
from typing import Any

import pandas as pd

from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.provenance.files import hash_file, write_bytes_atomic

PARQUET, CSV = "parquet", "csv"
# What pyarrow raises for a column it cannot store (its errors subclass these).
PARQUET_ERRORS = (ValueError, TypeError, NotImplementedError)


def find_collector(model: Model[Any, Any]) -> DataCollector | None:
    """The model's DataCollector: ``model.datacollector``, else the first attribute that is one."""
    collector = getattr(model, "datacollector", None)
    if isinstance(collector, DataCollector):
        return collector
    for value in vars(model).values():
        if isinstance(value, DataCollector):
            return value
    return None


def _flat(frame: pd.DataFrame) -> pd.DataFrame:
    """``frame`` with a named or multi-level index moved into columns."""
    if isinstance(frame.index, pd.RangeIndex) and frame.index.name is None:
        return frame.reset_index(drop=True)
    return frame.reset_index()


def collected_tables(model: Model[Any, Any]) -> dict[str, pd.DataFrame]:
    """Every non-empty table the model's DataCollector holds, by output name."""
    collector = find_collector(model)
    if collector is None:
        return {}
    tables = {}
    if collector.model_reporters:
        tables["model"] = collector.get_model_vars_dataframe()
    if collector.agent_reporters:
        tables["agents"] = collector.get_agent_vars_dataframe()
    for agent_type in collector.agenttype_reporters:
        name = f"agents_{agent_type.__name__}"
        tables[name] = collector.get_agenttype_vars_dataframe(agent_type)
    for name in collector.tables:
        tables[f"table_{name}"] = collector.get_table_dataframe(name)
    return {name: _flat(frame) for name, frame in tables.items()}


def parquet_available() -> bool:
    """True when pandas can write Parquet (pyarrow is installed)."""
    return importlib.util.find_spec("pyarrow") is not None


def _encode(frame: pd.DataFrame, form: str) -> bytes:
    """``frame`` serialised as ``form``, without the index."""
    if form == PARQUET:
        buffer = io.BytesIO()
        frame.to_parquet(buffer, index=False)
        return buffer.getvalue()
    text: str = frame.to_csv(index=False, lineterminator="\n")
    return text.encode("utf-8")


def write_table(
    frame: pd.DataFrame, folder: Path, name: str, form: str | None
) -> dict[str, Any]:
    """Write one table and return its output record; ``form`` None picks the best one."""
    form = form or (PARQUET if parquet_available() else CSV)
    try:
        data = _encode(frame, form)
    except PARQUET_ERRORS:
        if form != PARQUET:
            raise
        form, data = CSV, _encode(frame, CSV)
    path = Path(folder) / f"{name}.{form}"
    write_bytes_atomic(path, data)
    return {
        "columns": [str(column) for column in frame.columns],
        "format": form,
        "hash": hash_file(path),
        "path": path.name,
        "rows": len(frame),
        "table": name,
    }


def write_tables(
    tables: dict[str, pd.DataFrame],
    folder: Path,
    forms: dict[str, str] | None = None,
) -> list[Any]:
    """Write every table; ``forms`` maps a table name to the format to reuse."""
    forms = forms or {}
    return [
        write_table(frame, folder, name, forms.get(name))
        for name, frame in sorted(tables.items())
    ]


def read_table(path: Path, form: str) -> pd.DataFrame:
    """A table written by :func:`write_table`."""
    if form == PARQUET:
        return pd.read_parquet(path)
    return pd.read_csv(path, encoding="utf-8")
