"""Tests for the SLURM and PBS executors with a stand-in submit command.

No cluster is needed: ``subprocess.run`` is replaced by a function that
records the call and, like a scheduler, runs every array element through the
worker entry point in this process.
"""

import subprocess
from pathlib import Path

import pytest

from modelly.experiments import Experiment, ScenarioSpace
from modelly.experiments.executors import cluster
from modelly.experiments.executors.cluster import PBSExecutor, SlurmExecutor
from modelly.experiments.worker import load_tasks
from modelly.experiments.worker import main as worker_main
from tests.experiments.executors.shared import experiment
from tests.experiments.models import Walk

pytest.importorskip("pyarrow")
pytest.importorskip("duckdb")


class Scheduler:
    """Stands in for sbatch / qsub: records the call, optionally runs the array."""

    def __init__(self, output="4242\n", execute=True):  # noqa: D107
        self.output, self.execute, self.calls = output, execute, []

    def __call__(self, args, cwd, **options):  # noqa: D102
        self.calls.append((args, Path(cwd)))
        tasks_file = Path(cwd) / cluster.TASKS_FILE
        if self.execute:
            for index in range(len(load_tasks(tasks_file))):
                worker_main([str(tasks_file), str(index)])
        return subprocess.CompletedProcess(args, 0, stdout=self.output, stderr="")


@pytest.fixture
def scheduler(monkeypatch):
    """A scheduler that runs the job array at submission."""
    fake = Scheduler(output="4242;main\n")
    monkeypatch.setattr(cluster.subprocess, "run", fake)
    return fake


def script_of(scheduler):
    """The text of the last submitted script, and its raw bytes."""
    args, cwd = scheduler.calls[-1]
    path = cwd / args[-1]
    return path.read_text(encoding="utf-8"), path.read_bytes()


def test_slurm_job_array_runs_like_serial(tmp_path, scheduler):
    """Submitting through sbatch and waiting gives the serial numbers."""
    reference = experiment(tmp_path / "serial")
    reference.run("serial")
    run = experiment(tmp_path / "slurm")
    options = {"queue": "short", "walltime": "00:10:00", "memory": "1G"}
    executor = SlurmExecutor(
        submit_command="sbatch", wait=True, poll_interval=0, **options
    )
    report = run.run(executor, max_parallel=3)
    assert report.ok and report.done == 8 and executor.job_id == "4242"
    assert run.results().df().equals(reference.results().df())
    assert scheduler.calls[-1][0][:2] == ["sbatch", "--parsable"]
    text, raw = script_of(scheduler)
    assert b"\r\n" not in raw and text.startswith("#!/bin/bash\n")
    for line in ("--array=0-7%3", "--partition=short", "--time=00:10:00", "--mem=1G"):
        assert f"#SBATCH {line}\n" in text
    assert "-m modelly.experiments.worker" in text and "SLURM_ARRAY_TASK_ID" in text


def test_pbs_script_and_single_task(tmp_path, scheduler):
    """PBS uses -J and max_run_subjobs; one run needs no array."""
    run = experiment(tmp_path)
    executor = PBSExecutor(
        submit_command="qsub",
        queue="workq",
        account="proj",
        setup=["module load python"],
    )
    assert run.run(executor, max_parallel=2).total == 8
    text, _ = script_of(scheduler)
    for line in ("-J 0-7", "-W max_run_subjobs=2", "-q workq", "-A proj"):
        assert f"#PBS {line}\n" in text
    assert "module load python\n" in text and "PBS_ARRAY_INDEX" in text
    single = PBSExecutor().scheduler_lines(1, None, tmp_path)
    assert not any(line.startswith("-J") for line in single)


def test_without_wait_run_returns_at_submission(tmp_path, monkeypatch):
    """With wait=False the runs appear later; a rerun collects nothing new to do."""
    pending = Scheduler(execute=False)
    monkeypatch.setattr(cluster.subprocess, "run", pending)
    run = experiment(tmp_path)
    report = run.run(SlurmExecutor(submit_command="sbatch"))
    assert report.done == 0 and not run.store.finished()
    tasks_file = pending.calls[-1][1] / cluster.TASKS_FILE
    for index in range(8):  # the cluster runs the array later
        assert worker_main([str(tasks_file), str(index)]) == 0
    assert run.run("serial").skipped == 8


def test_failures_and_timeouts_while_waiting(tmp_path, monkeypatch, scheduler):
    """A failing element reads as a failed run; an array that never runs times out."""
    failing = Experiment(
        Walk,
        ScenarioSpace(fail=True, n=2),
        outputs="mean",
        steps=3,
        store=tmp_path / "f",
    )
    report = failing.run(
        SlurmExecutor(submit_command="sbatch", wait=True, poll_interval=0)
    )
    assert len(report.failed) == 1 and "asked to fail" in report.failed[0].error
    monkeypatch.setattr(cluster.subprocess, "run", Scheduler(execute=False))
    stuck = SlurmExecutor(
        submit_command="sbatch", wait=True, poll_interval=0, timeout=0
    )
    with pytest.raises(TimeoutError, match="unfinished"):
        experiment(tmp_path / "stuck").run(stuck)


def test_missing_submit_command(tmp_path, monkeypatch):
    """Without sbatch on PATH the error says where to run."""
    monkeypatch.setattr(cluster.shutil, "which", lambda name: None)
    with pytest.raises(FileNotFoundError, match="login node"):
        experiment(tmp_path).run("slurm")


def test_worker_reads_the_array_index_from_the_environment(tmp_path, monkeypatch):
    """The worker takes $SLURM_ARRAY_TASK_ID or $PBS_ARRAY_INDEX; bad input exits 2."""
    run = experiment(tmp_path)
    tasks_file = run.store.path / "tasks.json"
    folder = SlurmExecutor().prepare(run.tasks(), None, run.store.path)
    assert folder.parent / cluster.TASKS_FILE == tasks_file
    monkeypatch.setenv("PBS_ARRAY_INDEX", "5")
    assert worker_main([str(tasks_file)]) == 0
    assert run.store.finished() == {run.tasks()[5].seed}
    assert worker_main([]) == 2
    assert worker_main([str(tasks_file), "99"]) == 2
    monkeypatch.delenv("PBS_ARRAY_INDEX")
    assert worker_main([str(tasks_file)]) == 2
