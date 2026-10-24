"""Tests for one run: seeds, model and output references, simulate and run_task."""

import json
import textwrap

import numpy as np
import pytest

from modelly.experiments.store import KEYS, ResultsStore
from modelly.experiments.tasks import (
    DONE,
    FAILED,
    RunTask,
    reference,
    resolve,
    run_seed,
    run_task,
    simulate,
    spawn_safe,
)
from tests.experiments import models

pytest.importorskip("pyarrow")

WALK = "tests.experiments.models:Walk"
PLAIN = "tests.experiments.models:Plain"


def make_task(tmp_path, model=WALK, params=None, outputs=None, **extra):
    """A task over the test models."""
    return RunTask(
        model=model,
        params={"drift": 0.5, "n": 4} if params is None else params,
        point=2,
        replicate=1,
        entropy=11,
        steps=3,
        outputs={"mean": "mean", "spread": "spread"} if outputs is None else outputs,
        store=str(tmp_path),
        **extra,
    )


def test_seed_is_the_spawned_child():
    """The run's stream is SeedSequence(seed).spawn(...)[point].spawn(...)[replicate]."""
    task = RunTask(
        WALK, {}, point=3, replicate=2, entropy=5, steps=1, outputs={}, store="."
    )
    child = np.random.SeedSequence(5).spawn(4)[3].spawn(3)[2]
    assert np.array_equal(
        task.seed_sequence().generate_state(4), child.generate_state(4)
    )
    assert task.seed == run_seed(5, 3, 2)
    assert 0 <= task.seed < 2**63
    assert run_seed(5, 3, 2) != run_seed(5, 2, 3) != run_seed(6, 3, 2)


def test_references_resolve_and_flag_unimportable_objects():
    """A reference names an object by module:qualname; spawn_safe spots notebooks and lambdas."""
    assert reference(models.Walk) == WALK
    assert resolve(WALK) is models.Walk
    assert resolve("tests.experiments.models:Walk.mean") is models.Walk.mean
    assert spawn_safe(WALK)
    assert not spawn_safe("__main__:Walk")
    assert not spawn_safe(reference(lambda model: 0))


def test_a_model_file_is_imported_by_path(tmp_path):
    """A ``path.py:Class`` reference imports the file under a name of its own."""
    source = tmp_path / "file_model.py"
    source.write_text(
        textwrap.dedent(
            """
            from modelly import Model

            class Counter(Model):
                def __init__(self, rng=None):
                    super().__init__(rng=rng)
                    self.count = 0

                def step(self):
                    self.count += 1
            """
        ),
        encoding="utf-8",
    )
    ref = f"{source}:Counter"
    assert resolve(ref) is resolve(ref)
    table = simulate(make_task(tmp_path, ref, params={}, outputs={"count": "count"}))
    assert table.column("count").to_pylist() == [0, 1, 2, 3]


def test_simulate_rows_and_columns(tmp_path):
    """Keys, parameters, step and outputs, one row per step from step 0."""
    table = simulate(make_task(tmp_path))
    assert table.column_names == [*KEYS, "drift", "n", "step", "mean", "spread"]
    assert table.column("step").to_pylist() == [0, 1, 2, 3]
    assert table.column("run_id").to_pylist() == ["2-1"] * 4
    assert simulate(make_task(tmp_path)).equals(table)


def test_outputs_by_path_and_function(tmp_path):
    """Outputs may be dotted attribute paths or module:function references."""
    outputs = {
        "drift": "scenario.drift",
        "first": "tests.experiments.models:first_position",
    }
    task = make_task(tmp_path, params={"n": 2}, outputs=outputs)
    table = simulate(task)
    assert table.column("drift").to_pylist() == [0.0] * 4


def test_run_stops_when_the_model_does(tmp_path):
    """A model setting running = False ends the run early."""
    task = make_task(tmp_path, PLAIN, {"stop_at": 2}, {"value": "value"})
    assert simulate(task).column("step").to_pylist() == [0, 1, 2]


def test_run_task_retries_then_succeeds(tmp_path):
    """A run failing once succeeds on its retry and reports two attempts."""
    models.ATTEMPTS.clear()
    outputs = {"value": "tests.experiments.models:flaky_value"}
    task = make_task(tmp_path, PLAIN, {"rate": 0.25}, outputs, retries=1)
    outcome = run_task(task)
    assert (outcome.status, outcome.attempts) == (DONE, 2)
    assert ResultsStore(tmp_path).finished() == {task.seed}


def test_run_task_records_a_failure(tmp_path):
    """A run that keeps failing is recorded, with its traceback, unless told not to."""
    outputs = {"bad": "tests.experiments.models:not_a_scalar"}
    outcome = run_task(make_task(tmp_path, PLAIN, {}, outputs))
    assert outcome.status == FAILED
    assert "must be a number" in outcome.error
    record = json.loads(
        ResultsStore(tmp_path).failure_path(outcome.seed).read_text("utf-8")
    )
    assert record["run_id"] == "2-1" and record["attempts"] == 1
    quiet = run_task(
        make_task(tmp_path / "q", PLAIN, {}, outputs, record_failures=False)
    )
    assert quiet.status == FAILED and not ResultsStore(tmp_path / "q").failed()


def test_tasks_round_trip_through_json(tmp_path):
    """to_dict / from_dict survive JSON, so a job array can read them."""
    task = make_task(tmp_path, retries=2)
    again = RunTask.from_dict(json.loads(json.dumps(task.to_dict())))
    assert again == task and again.seed == task.seed
