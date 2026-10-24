"""Tests for the serial, thread and process executors: identical results, spawn safety."""

import pytest

from modelly.experiments.executors.local import ProcessExecutor, ThreadExecutor
from tests.experiments.executors.shared import MAX_PARALLEL, experiment

pytest.importorskip("pyarrow")
pytest.importorskip("duckdb")


@pytest.fixture(scope="module")
def serial_frame(tmp_path_factory):
    """The reference results, run in this process."""
    reference = experiment(tmp_path_factory.mktemp("serial"))
    reference.run("serial")
    return reference.results().df()


@pytest.mark.parametrize("name", ["threads", "processes"])
def test_identical_results(name, tmp_path, serial_frame):
    """Threads and spawn-started processes give the serial numbers, bit for bit."""
    run = experiment(tmp_path)
    report = run.run(name, max_parallel=MAX_PARALLEL)
    assert report.ok and report.done == 8
    assert run.results().df().equals(serial_frame)


def test_processes_refuse_what_a_worker_cannot_import(tmp_path):
    """A lambda output is fine on threads but refused before processes start."""
    run = experiment(tmp_path, outputs={"x": lambda model: 1.0})
    with pytest.raises(TypeError, match="cannot import"):
        run.run("processes", max_parallel=MAX_PARALLEL)
    assert run.run("threads", max_parallel=MAX_PARALLEL).ok


def test_empty_task_lists():
    """Nothing to run is not an error for the pool executors."""
    assert list(ProcessExecutor().run([])) == []
    assert list(ThreadExecutor().run([])) == []
