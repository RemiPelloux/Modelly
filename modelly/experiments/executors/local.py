"""Executors on this machine: serial, a thread pool and a process pool.

The process pool starts its workers with ``forkserver`` where it exists and
``spawn`` elsewhere (Windows, macOS), as ``modelly.batch.run_batch`` does: each
worker imports the model by its module path, so the same script runs on every
platform. Scripts need the usual ``if __name__ == "__main__":`` guard.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from concurrent.futures import (
    Executor as PoolExecutor,
)
from concurrent.futures import (
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)

from modelly.batch.runs import default_workers, worker_context
from modelly.experiments.executors import Executor
from modelly.experiments.tasks import RunOutcome, RunTask, run_task


class SerialExecutor(Executor):
    """Every run in this process, in task order."""

    name = "serial"
    in_process = True

    def run(
        self, tasks: Sequence[RunTask], max_parallel: int | None = None
    ) -> Iterator[RunOutcome]:
        """Run the tasks one after another."""
        for task in tasks:
            yield run_task(task)


def _pool_outcomes(
    pool: PoolExecutor, tasks: Sequence[RunTask]
) -> Iterator[RunOutcome]:
    """Submit every task to ``pool``; yield outcomes as they finish; cancel the rest on exit."""
    try:
        futures = [pool.submit(run_task, task) for task in tasks]
        for future in as_completed(futures):
            yield future.result()
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


def _workers(max_parallel: int | None, tasks: Sequence[RunTask]) -> int:
    """``max_parallel`` (else ``default_workers()``), at most one per task."""
    workers = default_workers() if max_parallel is None else max_parallel
    return max(1, min(workers, len(tasks)))


class ThreadExecutor(Executor):
    """A thread pool: parallel on free-threaded Python, concurrent otherwise."""

    name = "threads"
    in_process = True

    def run(
        self, tasks: Sequence[RunTask], max_parallel: int | None = None
    ) -> Iterator[RunOutcome]:
        """Run the tasks on up to ``max_parallel`` threads."""
        if not tasks:
            return iter(())
        pool = ThreadPoolExecutor(max_workers=_workers(max_parallel, tasks))
        return _pool_outcomes(pool, tasks)


class ProcessExecutor(Executor):
    """A pool of worker processes that import the model (spawn-safe)."""

    name = "processes"

    def run(
        self, tasks: Sequence[RunTask], max_parallel: int | None = None
    ) -> Iterator[RunOutcome]:
        """Run the tasks on up to ``max_parallel`` processes."""
        if not tasks:
            return iter(())
        self.check(tasks)
        pool = ProcessPoolExecutor(
            max_workers=_workers(max_parallel, tasks), mp_context=worker_context()
        )
        return _pool_outcomes(pool, tasks)
