"""Tests for Experiment: schema, determinism, resume after a crash and failure handling."""

import pytest

from modelly.experiments import (
    Executor,
    Experiment,
    ExperimentError,
    ScenarioSpace,
    StoreMismatchError,
    designs,
)
from modelly.experiments.tasks import run_task
from tests.experiments.models import Plain, Walk

pytest.importorskip("pyarrow")
pytest.importorskip("duckdb")

SPACE = ScenarioSpace(drift=(0.0, 1.0), policy=["a", "b"], n=5)


def walk(store, **overrides):
    """A small experiment over the Walk model."""
    settings = {"design": designs.latin_hypercube(4), "replicates": 2, "steps": 4}
    settings |= {"outputs": ["mean", "spread"], "store": store, "seed": 3}
    return Experiment(Walk, SPACE, **(settings | overrides))


class Crash(Executor):
    """Runs ``limit`` tasks, then dies as a killed process would."""

    name = "crash"
    in_process = True

    def __init__(self, limit):  # noqa: D107
        self.limit = limit

    def run(self, tasks, max_parallel=None):  # noqa: D102
        for task in tasks[: self.limit]:
            yield run_task(task)
        raise KeyboardInterrupt


class Reversed(Executor):
    """Runs the tasks last first."""

    name = "reversed"
    in_process = True

    def run(self, tasks, max_parallel=None):  # noqa: D102
        for task in reversed(tasks):
            yield run_task(task)


def test_results_schema(tmp_path):
    """One row per run and step: keys, parameters, step, outputs."""
    experiment = walk(tmp_path)
    report = experiment.run("serial")
    assert (report.total, report.done, report.skipped, report.ok) == (8, 8, 0, True)
    frame = experiment.results().df()
    expected = ["run_id", "point", "replicate", "seed", "drift", "policy", "n"]
    assert list(frame.columns) == [*expected, "step", "mean", "spread"]
    assert len(frame) == 8 * 5
    assert frame.groupby("seed").size().eq(5).all()
    assert str(frame["seed"].dtype) == "int64" and str(frame["step"].dtype) == "int64"
    sql = "SELECT policy, count(DISTINCT run_id) FROM runs GROUP BY policy ORDER BY policy"
    assert sum(n for _, n in experiment.results().query(sql).fetchall()) == 8


def test_same_seed_same_numbers_in_any_order(tmp_path):
    """Results depend on the seed only, not on the order runs execute in."""
    first, second = walk(tmp_path / "a"), walk(tmp_path / "b")
    first.run("serial")
    second.run(Reversed())
    assert first.results().df().equals(second.results().df())
    other = walk(tmp_path / "c", seed=4)
    other.run("serial")
    assert not other.results().df()["mean"].equals(first.results().df()["mean"])


def test_resume_after_a_crash_skips_finished_runs(tmp_path):
    """A killed sweep keeps its finished runs; the rerun does only the rest."""
    experiment = walk(tmp_path / "crashed")
    with pytest.raises(KeyboardInterrupt):
        experiment.run(Crash(limit=3))
    (tmp_path / "crashed" / ".run-1.parquet.dead.tmp").write_bytes(b"half a file")
    assert len(experiment.store.finished()) == 3
    resumed = walk(tmp_path / "crashed").run("serial")
    assert (resumed.skipped, resumed.done) == (3, 5)
    straight = walk(tmp_path / "straight")
    straight.run("serial")
    assert experiment.results().df().equals(straight.results().df())
    assert walk(tmp_path / "crashed").run("serial").done == 0


def test_more_replicates_reuse_the_store(tmp_path):
    """Growing replicates runs only the new ones; another seed is refused."""
    walk(tmp_path, replicates=1).run("serial")
    report = walk(tmp_path, replicates=3).run("serial")
    assert (report.skipped, report.done) == (4, 8)
    with pytest.raises(StoreMismatchError):
        walk(tmp_path, seed=9).run("serial")


def test_failures_record_skip_and_raise(tmp_path):
    """On error, record keeps a failure file, skip does not, raise stops with ExperimentError."""
    failing = ScenarioSpace(fail=[False, True], n=2)
    setup = {"design": designs.full_factorial(), "replicates": 1, "steps": 3}
    recorded = Experiment(Walk, failing, outputs="mean", store=tmp_path / "r", **setup)
    report = recorded.run("serial")
    assert (report.done, len(report.failed)) == (1, 1)
    failures = recorded.failures()
    assert failures.loc[0, "params"] == {"fail": True, "n": 2}
    assert "asked to fail" in failures.loc[0, "error"]
    skipped = Experiment(
        Walk, failing, outputs="mean", store=tmp_path / "s", on_error="skip", **setup
    )
    assert not skipped.run("serial").ok and skipped.failures().empty
    raising = Experiment(
        Walk, failing, outputs="mean", store=tmp_path / "x", on_error="raise", **setup
    )
    with pytest.raises(ExperimentError, match="asked to fail"):
        raising.run("serial")


def test_retries_count_attempts(tmp_path):
    """Each retry gives a failing run more attempts before it counts as failed."""
    failing = ScenarioSpace(fail=True, n=2)
    experiment = Experiment(Walk, failing, outputs="mean", store=tmp_path, retries=2)
    report = experiment.run("serial")
    assert report.failed[0].attempts == 3


def test_model_without_scenario_and_progress(tmp_path):
    """Parameters go to the constructor of a model with no Scenario; progress is reported."""
    seen = []
    experiment = Experiment(
        Plain,
        ScenarioSpace(rate=[1.0, 2.0]),
        replicates=2,
        steps=2,
        outputs={"value": "value"},
        store=tmp_path,
    )
    experiment.run("serial", progress=lambda done, total, outcome: seen.append(done))
    assert seen == [1, 2, 3, 4]
    assert experiment.results().query("SELECT max(rate) FROM runs").fetchall() == [
        (2.0,)
    ]
    assert experiment.run("threads", progress=True).skipped == 4


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"on_error": "ignore"}, "on_error"),
        ({"replicates": 0}, "replicates"),
        ({"seed": -1}, "non-negative"),
        ({"outputs": ["step"]}, "reserved"),
        ({"outputs": ["policy"]}, "used twice"),
        ({"outputs": []}, "at least one output"),
    ],
)
def test_invalid_experiments(tmp_path, overrides, message):
    """Settings that cannot make a study are rejected up front."""
    with pytest.raises(ValueError, match=message):
        walk(tmp_path, **overrides)


def test_space_is_typed_against_the_scenario(tmp_path):
    """A parameter the Scenario does not declare is an error before anything runs."""
    with pytest.raises(ValueError, match="declares no parameter"):
        Experiment(
            Walk, ScenarioSpace(speed=(0.0, 1.0)), outputs="mean", store=tmp_path
        )
