"""The Ray executor: runs on a Ray cluster through its public task API.

``ray.init`` is called when Ray is not initialised yet (a local cluster with
no ``address``) and ``ray.shutdown`` afterwards; an initialised Ray is used
as it is and left running. Workers import the model by its module path and
write the run's Parquet file themselves, so the store must be on a shared
filesystem. Needs ``pip install "modelly-abm[ray]"``.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from itertools import islice
from typing import Any

from modelly._optional import require
from modelly.batch.runs import default_workers
from modelly.experiments.executors import Executor
from modelly.experiments.tasks import RunOutcome, RunTask, run_task

EXTRA = "ray"


class RayExecutor(Executor):
    """Runs each task as a Ray remote function, at most ``max_parallel`` in flight.

    Args:
        address: the cluster to join (``"auto"``, ``"ray://host:10001"``...);
            ``None`` starts a local Ray.
        **init_options: extra ``ray.init`` arguments (``num_cpus``, ``runtime_env``...).

    Example:
        >>> experiment.run(executor="ray", address="auto")  # doctest: +SKIP
    """

    name = "ray"

    def __init__(self, address: str | None = None, **init_options: Any) -> None:
        """Keep where to connect; nothing starts before ``run``."""
        self.address = address
        self.init_options = init_options

    def run(
        self, tasks: Sequence[RunTask], max_parallel: int | None = None
    ) -> Iterator[RunOutcome]:
        """Submit the tasks, keeping ``max_parallel`` in flight; yield outcomes."""
        if not tasks:
            return
        self.check(tasks)
        ray = require("ray", EXTRA)
        started = not ray.is_initialized()
        if started:
            ray.init(address=self.address, **self.init_options)
        try:
            yield from _bounded(ray, tasks, max_parallel or default_workers())
        finally:
            if started:
                ray.shutdown()


def _bounded(ray: Any, tasks: Sequence[RunTask], limit: int) -> Iterator[RunOutcome]:
    """Submit ``limit`` tasks, then one more each time ``ray.wait`` returns one."""
    remote = ray.remote(run_task)
    waiting = iter(tasks)
    pending = [remote.remote(task) for task in islice(waiting, limit)]
    while pending:
        done, pending = ray.wait(pending, num_returns=1)
        yield ray.get(done[0])
        following = next(waiting, None)
        if following is not None:
            pending = [*pending, remote.remote(following)]
