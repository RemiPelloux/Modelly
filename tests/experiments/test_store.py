"""Tests for the results store: atomic per-run files, failure records, the fingerprint."""

import pytest

from modelly.experiments.store import (
    ResultsStore,
    StoreMismatchError,
    write_text_atomic,
)

pa = pytest.importorskip("pyarrow")
pytest.importorskip("duckdb")


def table(seed, rows=2):
    """A small run table."""
    keys = {"point": [seed] * rows, "replicate": [0] * rows, "seed": [seed] * rows}
    return pa.table({**keys, "step": list(range(rows)), "x": [1.5] * rows})


def test_runs_are_files_named_by_seed(tmp_path):
    """write_run adds run-<seed>.parquet; finished lists the seeds; temp files are ignored."""
    store = ResultsStore(tmp_path / "store")
    assert store.finished() == set()
    store.write_run(7, table(7))
    store.write_run(12, table(12))
    (store.path / ".run-99.parquet.abc.tmp").write_bytes(b"partial")
    assert store.finished() == {7, 12}
    assert store.run_path(7).name == "run-7.parquet"


def test_failures_are_recorded_and_cleared(tmp_path):
    """record_failure keeps JSON; a later successful write removes it."""
    store = ResultsStore(tmp_path)
    assert store.failures().empty
    store.record_failure(3, {"seed": 3, "error": "boom", "attempts": 2})
    assert store.failed() == {3}
    assert store.failures().loc[0, "error"] == "boom"
    store.write_run(3, table(3))
    assert store.failed() == set()


def test_claim_refuses_another_experiment(tmp_path):
    """The first claim writes experiment.json; a different one is refused."""
    store = ResultsStore(tmp_path)
    store.claim({"seed": 1, "points": [{"a": 0.5}]})
    store.claim({"points": [{"a": 0.5}], "seed": 1})  # same content, any key order
    with pytest.raises(StoreMismatchError, match="different experiment"):
        store.claim({"seed": 2, "points": [{"a": 0.5}]})


def test_results_view(tmp_path):
    """Results reads every run file through the DuckDB view runs."""
    store = ResultsStore(tmp_path)
    with pytest.raises(LookupError, match="no finished runs"):
        store.results()
    store.write_run(1, table(1, rows=3))
    store.write_run(2, table(2, rows=2))
    results = store.results()
    assert len(results) == 5
    total = results.query("SELECT sum(x) AS s FROM runs").fetchall()[0][0]
    assert total == pytest.approx(7.5)
    assert results.arrow().num_rows == 5


def test_text_writes_are_atomic(tmp_path):
    """write_text_atomic creates folders and leaves only the final file."""
    target = tmp_path / "a" / "b.json"
    write_text_atomic(target, "{}")
    write_text_atomic(target, '{"x": 1}')
    assert target.read_text(encoding="utf-8") == '{"x": 1}'
    assert [p.name for p in target.parent.iterdir()] == ["b.json"]
