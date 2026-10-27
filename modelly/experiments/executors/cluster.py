"""SLURM and PBS executors: one job array per experiment, submitted with ``sbatch`` or ``qsub``.

``run`` writes, in ``<store>/jobs/<id>/``, a ``tasks.json`` (one task per array
element) and a ``job.sh`` whose every element runs
``python -m modelly.experiments.worker tasks.json $INDEX``, then submits the
script. The store must be on a filesystem the compute nodes share; workers
write each run's Parquet file there. With ``wait=True`` the executor polls the
store until every run has finished or failed; otherwise ``run`` returns once
the job is submitted and the results appear as the array runs (rerunning the
experiment skips what is finished, so it doubles as "collect").

Only ``sbatch`` / ``qsub`` are called (found on ``PATH``); the scripts are
bash for the Linux nodes and written with Unix line endings from any OS.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from modelly.experiments.executors import Executor
from modelly.experiments.store import ResultsStore, write_text_atomic
from modelly.experiments.tasks import DONE, FAILED, RunOutcome, RunTask

JOBS = "jobs"
TASKS_FILE = "tasks.json"
SCRIPT_FILE = "job.sh"
SHEBANG = "#!/bin/bash"
DEFAULT_PYTHON = "python3"
DEFAULT_POLL_SECONDS = 30.0
WORKER = "-m modelly.experiments.worker"


class ClusterExecutor(Executor):
    """A job array on a batch scheduler; subclasses set the directives.

    Args:
        job_name: the scheduler's job name.
        queue: the partition (SLURM) or queue (PBS).
        account: the account or project charged.
        walltime: the time limit of one array element (``"01:00:00"``).
        memory: memory per element (``"4G"`` / ``"4gb"``).
        cpus: CPUs per element.
        directives: extra scheduler lines, without the ``#SBATCH``/``#PBS`` prefix.
        setup: shell lines run before the worker (``module load python``...).
        python: the Python on the compute nodes.
        wait: poll the store until every run has finished or failed.
        poll_interval: seconds between polls; ``timeout``: give up after (seconds).
        submit_command: the submit program (default: found on ``PATH``).
    """

    name = "cluster"
    program = ""
    submit_flags: tuple[str, ...] = ()
    prefix = ""
    index_variable = ""

    def __init__(
        self,
        job_name: str = "modelly",
        queue: str | None = None,
        account: str | None = None,
        walltime: str | None = None,
        memory: str | None = None,
        cpus: int = 1,
        directives: Sequence[str] = (),
        setup: Sequence[str] = (),
        python: str = DEFAULT_PYTHON,
        wait: bool = False,
        poll_interval: float = DEFAULT_POLL_SECONDS,
        timeout: float | None = None,
        submit_command: str | None = None,
    ) -> None:
        """Keep the job's settings; nothing is written before ``run``."""
        self.job_name, self.queue, self.account = job_name, queue, account
        self.walltime, self.memory, self.cpus = walltime, memory, cpus
        self.directives, self.setup = list(directives), list(setup)
        self.python, self.wait = python, wait
        self.poll_interval, self.timeout = poll_interval, timeout
        self.submit_command = submit_command
        self.job_id: str | None = None

    def scheduler_lines(self, count: int, limit: int | None, folder: Path) -> list[str]:
        """The scheduler directives (without prefix) for ``count`` elements."""
        raise NotImplementedError

    def script(self, tasks_file: Path, count: int, limit: int | None) -> str:
        """The job script running element ``$INDEX`` of ``tasks_file``."""
        folder = tasks_file.parent
        lines = self.scheduler_lines(count, limit, folder) + self.directives
        header = [f"{self.prefix} {line}" for line in lines]
        index = f'"${{{self.index_variable}:-0}}"'
        command = f"{self.python} {WORKER} {shlex.quote(tasks_file.as_posix())} {index}"
        body = ["set -euo pipefail", *self.setup, command]
        return "\n".join([SHEBANG, *header, "", *body]) + "\n"

    def submit(self, script: Path) -> str:
        """Submit ``script``; the scheduler's job id."""
        program = self.submit_command or shutil.which(self.program)
        if program is None:
            raise FileNotFoundError(
                f"{self.program} is not on PATH: run on the cluster's login node, "
                "or pass submit_command="
            )
        done = subprocess.run(
            [program, *self.submit_flags, script.name],
            cwd=script.parent,
            capture_output=True,
            text=True,
            check=True,
        )
        return self.job_id_from(done.stdout)

    def job_id_from(self, output: str) -> str:
        """The job id in the submit command's output."""
        return output.strip()

    def run(
        self, tasks: Sequence[RunTask], max_parallel: int | None = None
    ) -> Iterator[RunOutcome]:
        """Write the job files, submit the array and, with ``wait``, poll the store."""
        if not tasks:
            return
        self.check(tasks)
        store = ResultsStore(tasks[0].store)
        for task in tasks:  # a stale record would read as this attempt's failure
            store.failure_path(task.seed).unlink(missing_ok=True)
        script = self.prepare(tasks, max_parallel, store.path / JOBS / uuid.uuid4().hex)
        self.job_id = self.submit(script)
        if self.wait:
            yield from self.poll(tasks, store)

    def prepare(
        self, tasks: Sequence[RunTask], limit: int | None, folder: Path
    ) -> Path:
        """Write ``tasks.json`` and ``job.sh`` in ``folder``; the script's path."""
        tasks_file = folder.resolve() / TASKS_FILE
        rows = [task.to_dict() for task in tasks]
        write_text_atomic(tasks_file, json.dumps(rows, indent=1))
        script = folder / SCRIPT_FILE
        with script.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(self.script(tasks_file, len(tasks), limit))
        return script

    def poll(
        self, tasks: Sequence[RunTask], store: ResultsStore
    ) -> Iterator[RunOutcome]:
        """Yield each task's outcome as its result or failure file appears."""
        waiting = {task.seed: task for task in tasks}
        deadline = None if self.timeout is None else time.monotonic() + self.timeout
        while waiting:
            for seed in [s for s in waiting if _settled(store, s)]:
                yield _outcome(store, waiting.pop(seed))
            if waiting:
                if deadline is not None and time.monotonic() > deadline:
                    raise TimeoutError(
                        f"{len(waiting)} runs of job {self.job_id} unfinished"
                    )
                time.sleep(self.poll_interval)


def _settled(store: ResultsStore, seed: int) -> bool:
    """Whether the run with ``seed`` has a result or a failure file."""
    return store.run_path(seed).is_file() or store.failure_path(seed).is_file()


def _outcome(store: ResultsStore, task: RunTask) -> RunOutcome:
    """The outcome the store records for ``task``."""
    if store.run_path(task.seed).is_file():
        return RunOutcome(task.run_id, task.seed, DONE)
    record: dict[str, Any] = json.loads(
        store.failure_path(task.seed).read_text(encoding="utf-8")
    )
    return RunOutcome(
        task.run_id, task.seed, FAILED, record["attempts"], record["error"]
    )


class SlurmExecutor(ClusterExecutor):
    """A SLURM job array (``sbatch --parsable``), ``%max_parallel`` elements at a time.

    Example:
        >>> experiment.run(executor="slurm", queue="short", max_parallel=500)  # doctest: +SKIP
    """

    name = "slurm"
    program = "sbatch"
    submit_flags = ("--parsable",)
    prefix = "#SBATCH"
    index_variable = "SLURM_ARRAY_TASK_ID"

    def scheduler_lines(self, count: int, limit: int | None, folder: Path) -> list[str]:
        """--job-name, --array, --output and the resources set."""
        throttle = f"%{limit}" if limit else ""
        lines = [f"--job-name={self.job_name}", f"--array=0-{count - 1}{throttle}"]
        lines += [f"--output={(folder / 'slurm-%A_%a.out').as_posix()}"]
        lines += [f"--cpus-per-task={self.cpus}"]
        options = (
            ("partition", self.queue),
            ("account", self.account),
            ("time", self.walltime),
            ("mem", self.memory),
        )
        return lines + [f"--{key}={value}" for key, value in options if value]

    def job_id_from(self, output: str) -> str:
        """``--parsable`` prints ``jobid[;cluster]``."""
        return output.strip().split(";")[0]


class PBSExecutor(ClusterExecutor):
    """A PBS Pro job array (``qsub -J``), with ``max_run_subjobs`` as the throttle.

    Example:
        >>> experiment.run(executor="pbs", queue="workq", walltime="02:00:00")  # doctest: +SKIP
    """

    name = "pbs"
    program = "qsub"
    prefix = "#PBS"
    index_variable = "PBS_ARRAY_INDEX"

    def scheduler_lines(self, count: int, limit: int | None, folder: Path) -> list[str]:
        """-N, -J, -j oe, -o and the resources set."""
        lines = [f"-N {self.job_name}", "-j oe", f"-o {folder.as_posix()}/"]
        if count > 1:  # PBS arrays need two subjobs or more; one runs as index 0
            lines += [f"-J 0-{count - 1}"]
            lines += [f"-W max_run_subjobs={limit}"] if limit else []
        resources = f"select=1:ncpus={self.cpus}" + (
            f":mem={self.memory}" if self.memory else ""
        )
        lines += [f"-l {resources}"]
        lines += [f"-l walltime={self.walltime}"] if self.walltime else []
        lines += [f"-q {self.queue}"] if self.queue else []
        return lines + ([f"-A {self.account}"] if self.account else [])
