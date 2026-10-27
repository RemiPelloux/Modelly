"""The results store: one Parquet file per finished run, a DuckDB view over them all.

Layout of a store folder::

    experiment.json          what the experiment is (model, design, seed...)
    run-<seed>.parquet       one finished run: one row per step
    failures/run-<seed>.json a run that raised, with its traceback

Every file is written to a temporary name and moved into place with
``os.replace``, so a killed sweep leaves only whole files and is resumed by
skipping the seeds already present. Rows have the columns of :data:`KEYS`, the
parameters, ``step`` and the outputs.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from modelly._optional import require

if TYPE_CHECKING:
    import duckdb
    import pyarrow as pa
from modelly.data.io import TEMP_SUFFIX, write_parquet_atomic

EXTRA = "experiments"
KEYS = ("run_id", "point", "replicate", "seed")
STEP = "step"
RESERVED = (*KEYS, STEP)
RUN_PREFIX = "run-"
RUN_SUFFIX = ".parquet"
FAILURES = "failures"
METADATA = "experiment.json"
VIEW = "runs"
ORDER = "point, replicate, step"


class StoreMismatchError(ValueError):
    """The store folder holds the results of a different experiment."""


def write_text_atomic(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` (UTF-8) through a temporary file and ``os.replace``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}{TEMP_SUFFIX}")
    try:
        temp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _canonical(document: Any) -> str:
    """``document`` as sorted, compact JSON, for comparing fingerprints."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), default=str)


class ResultsStore:
    """A folder of per-run Parquet files, append-only and resumable.

    Example:
        >>> store = ResultsStore("runs/epidemic")  # doctest: +SKIP
        >>> store.finished()  # the seeds already run  # doctest: +SKIP
    """

    def __init__(self, path: str | Path) -> None:
        """Use (and create on first write) the folder ``path``."""
        self.path = Path(path)

    def run_path(self, seed: int) -> Path:
        """The Parquet file of the run with ``seed``."""
        return self.path / f"{RUN_PREFIX}{seed}{RUN_SUFFIX}"

    def failure_path(self, seed: int) -> Path:
        """The failure record of the run with ``seed``."""
        return self.path / FAILURES / f"{RUN_PREFIX}{seed}.json"

    def finished(self) -> set[int]:
        """The seeds of every run with a results file."""
        if not self.path.is_dir():
            return set()
        names = (p.name for p in self.path.glob(f"{RUN_PREFIX}*{RUN_SUFFIX}"))
        return {int(name[len(RUN_PREFIX) : -len(RUN_SUFFIX)]) for name in names}

    def write_run(self, seed: int, table: Any) -> Path:
        """Store a finished run's ``pyarrow.Table``; clear any earlier failure record."""
        path = write_parquet_atomic(table, self.run_path(seed))
        self.failure_path(seed).unlink(missing_ok=True)
        return path

    def record_failure(self, seed: int, record: dict[str, Any]) -> None:
        """Keep a failed run's details (error, traceback, attempts) as JSON."""
        text = json.dumps(record, indent=2, default=str)
        write_text_atomic(self.failure_path(seed), text)

    def failed(self) -> set[int]:
        """The seeds of every run with a failure record."""
        folder = self.path / FAILURES
        names = (p.stem for p in folder.glob(f"{RUN_PREFIX}*.json"))
        return {int(name[len(RUN_PREFIX) :]) for name in names}

    def failures(self) -> pd.DataFrame:
        """One row per recorded failure, in seed order."""
        records = [
            json.loads(self.failure_path(seed).read_text(encoding="utf-8"))
            for seed in sorted(self.failed())
        ]
        return pd.DataFrame.from_records(records)

    def claim(self, fingerprint: dict[str, Any]) -> None:
        """Record what experiment writes here; refuse a store holding another one."""
        metadata = self.path / METADATA
        if metadata.is_file():
            stored = json.loads(metadata.read_text(encoding="utf-8"))
            if _canonical(stored) != _canonical(fingerprint):
                raise StoreMismatchError(
                    f"{self.path} holds the results of a different experiment "
                    f"(see {METADATA}); use another store or delete it"
                )
            return
        write_text_atomic(metadata, json.dumps(fingerprint, indent=2, default=str))

    def results(self) -> Results:
        """The finished runs, as a DuckDB view named ``runs``."""
        return Results(self)


class Results:
    """SQL over a store's runs: ``query`` returns a DuckDB relation.

    Example:
        >>> results.query("SELECT beta, avg(infected) FROM runs GROUP BY beta").df()  # doctest: +SKIP
    """

    def __init__(self, store: ResultsStore) -> None:
        """Open an in-memory DuckDB connection with the view ``runs`` over the store."""
        if not store.finished():
            raise LookupError(f"no finished runs in {store.path}")
        duckdb = require("duckdb", EXTRA)
        self.connection = duckdb.connect()
        pattern = (store.path / f"{RUN_PREFIX}*{RUN_SUFFIX}").as_posix()
        quoted = pattern.replace("'", "''")
        self.connection.sql(
            f"CREATE VIEW {VIEW} AS SELECT * FROM "  # noqa: S608 (a local path)
            f"read_parquet('{quoted}', union_by_name = true)"
        )

    def query(self, sql: str) -> duckdb.DuckDBPyRelation:
        """Run ``sql`` (which reads the view ``runs``); a DuckDB relation."""
        relation: duckdb.DuckDBPyRelation = self.connection.sql(sql)
        return relation

    @property
    def relation(self) -> duckdb.DuckDBPyRelation:
        """Every row, ordered by point, replicate and step."""
        return self.query(f"SELECT * FROM {VIEW} ORDER BY {ORDER}")  # noqa: S608

    def df(self) -> pd.DataFrame:
        """Every row as a pandas DataFrame, ordered by point, replicate and step."""
        return self.relation.df()

    def arrow(self) -> pa.Table:
        """Every row as a ``pyarrow.Table``, ordered by point, replicate and step."""
        return self.relation.to_arrow_table()

    def __len__(self) -> int:
        """The number of rows (runs times steps)."""
        rows = self.query(f"SELECT count(*) FROM {VIEW}").fetchall()  # noqa: S608
        count: int = rows[0][0]
        return count
