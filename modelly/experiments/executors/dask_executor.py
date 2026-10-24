"""The Dask executor: runs on a ``dask.distributed`` cluster.

With no ``address`` or ``client`` it starts a local cluster of worker
processes (one thread each, no dashboard, bound to 127.0.0.1) and closes it
afterwards; with one, it uses that cluster and leaves it running. Workers
import the model by its module path, and write the run's Parquet file to the
store themselves, so the store must be on a filesystem they share.
Needs ``pip install "modelly-abm[dask]"``.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from itertools import islice
from typing import Any

from modelly._optional import require
from modelly.batch.runs import default_workers
from modelly.experiments.executors import Executor
from modelly.experiments.tasks import RunOutcome, RunTask, run_task

EXTRA = "dask"
LOCALHOST = "127.0.0.1"


class DaskExecutor(Executor):
    """Runs on a Dask cluster, at most ``max_parallel`` runs in flight.

    Args:
        address: a scheduler address to connect to.
        client: an existing ``distributed.Client`` (kept open).
        **cluster_options: extra ``LocalCluster`` arguments for the local cluster.

    Example:
        >>> experiment.run(executor="dask", address="tcp://scheduler:8786")  # doctest: +SKIP
    """

    name = "dask"

    def __init__(
        self, address: str | None = None, client: Any = None, **cluster_options: Any
    ) -> None:
        """Keep where to connect; nothing starts before ``run``."""
        self.address = address
        self.client = client
        self.cluster_options = cluster_options

    def _connect(self, distributed: Any, workers: int) -> tuple[Any, list[Any]]:
        """The client to use and the objects to close afterwards."""
        if self.client is not None:
            return self.client, []
        if self.address is not None:
            client = distributed.Client(self.address)
            return client, [client]
        options = {"n_workers": workers, "threads_per_worker": 1, "processes": True}
        options |= {"dashboard_address": None, "host": LOCALHOST}
        cluster = distributed.LocalCluster(**(options | self.cluster_options))
        client = distributed.Client(cluster)
        return client, [client, cluster]

    def run(
        self, tasks: Sequence[RunTask], max_parallel: int | None = None
    ) -> Iterator[RunOutcome]:
        """Submit the tasks, keeping ``max_parallel`` in flight; yield outcomes."""
        if not tasks:
            return
        self.check(tasks)
        distributed = require("distributed", EXTRA)
        limit = max_parallel or default_workers()
        client, owned = self._connect(distributed, min(limit, len(tasks)))
        try:
            yield from _bounded(distributed, client, tasks, limit)
        finally:
            for item in owned:
                item.close()


def _bounded(
    distributed: Any, client: Any, tasks: Sequence[RunTask], limit: int
) -> Iterator[RunOutcome]:
    """Submit ``limit`` tasks, then one more each time one finishes."""
    waiting = iter(tasks)

    def submit(task: RunTask) -> Any:
        return client.submit(run_task, task, pure=False)

    running = distributed.as_completed([submit(t) for t in islice(waiting, limit)])
    for future in running:
        yield future.result()
        following = next(waiting, None)
        if following is not None:
            running.add(submit(following))
