"""A process executor that keeps its workers between batches.

ABC-SMC, simulated moments and Bayesian optimisation submit many small
batches. The experiments' ``processes`` executor starts a fresh pool for each
``run`` call (workers start with ``forkserver`` or ``spawn`` and import the
model: about a second each time); this one starts it once and reuses it until
``close``. Its outcomes are the same, task for task.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from typing import Any

from modelly.batch.runs import default_workers, worker_context
from modelly.experiments.executors.local import ProcessExecutor, _submit_chunks
from modelly.experiments.tasks import RunOutcome, RunTask


class PooledProcessExecutor(ProcessExecutor):
    """``processes``, with one pool for every ``run`` call until ``close``."""

    def __init__(self, **options: Any) -> None:
        """No pool until the first batch."""
        super().__init__(**options)
        self._pool: ProcessPoolExecutor | None = None
        self._workers = 1

    def run(
        self, tasks: Sequence[RunTask], max_parallel: int | None = None
    ) -> Iterator[RunOutcome]:
        """Run the tasks on the shared pool (sized by the first call's ``max_parallel``)."""
        if not tasks:
            return
        self.check(tasks)
        if self._pool is None:
            workers = default_workers() if max_parallel is None else max_parallel
            self._workers = max(1, workers)
            self._pool = ProcessPoolExecutor(
                max_workers=self._workers, mp_context=worker_context()
            )
        yield from _submit_chunks(self._pool, tasks, self._workers)

    def close(self) -> None:
        """Stop the workers."""
        if self._pool is not None:
            self._pool.shutdown(wait=True, cancel_futures=True)
            self._pool = None
