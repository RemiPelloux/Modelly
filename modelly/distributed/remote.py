"""Split runs on Dask or Ray: each partition is an actor on a worker process.

The process that builds the model is the coordinator: it calls every actor in
parallel and passes the ghosts and migrants between them, so the bytes of an
exchange travel through it. That keeps the protocol identical to the MPI one,
at the price of a round trip per exchange; for many partitions on a cluster
prefer MPI, where neighbours talk directly.

``DaskGroup`` starts a local cluster of one-thread worker processes (bound to
127.0.0.1, no dashboard) unless given an ``address`` or a ``client``, and
places one actor on each worker. ``RayGroup`` calls ``ray.init`` when Ray is
not running yet and shuts it down afterwards. Both import their library only
when used: ``pip install "modelly-abm[dask]"`` or ``"modelly-abm[ray]"``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from modelly._optional import require
from modelly.distributed.groups import Outboxes, transpose
from modelly.distributed.worker import BuildRequest, PartitionWorker

LOCALHOST = "127.0.0.1"


class _CoordinatedGroup:
    """The coordinator side shared by Dask and Ray: every actor is reachable here."""

    is_root = True
    actors: list[Any]

    def _wait(self, calls: list[Any]) -> list[Any]:
        """The results of the calls, in partition order."""
        raise NotImplementedError

    def invoke(self, method: str, *args: Any) -> dict[int, Any]:
        """Call ``method(*args)`` on every actor, in parallel."""
        calls = [self._call(actor, method, args) for actor in self.actors]
        return dict(enumerate(self._wait(calls)))

    def deliver(self, method: str, payloads: dict[int, Any]) -> dict[int, Any]:
        """Call ``method(payloads[i])`` on actor ``i``, in parallel."""
        calls = [
            self._call(actor, method, (payloads[i],))
            for i, actor in enumerate(self.actors)
        ]
        return dict(enumerate(self._wait(calls)))

    def _call(self, actor: Any, method: str, args: tuple) -> Any:
        """Start ``actor.method(*args)``; a handle for ``_wait``."""
        raise NotImplementedError

    @staticmethod
    def exchange(outboxes: Outboxes) -> Outboxes:
        """Route every outbox to its receivers."""
        return transpose(outboxes)

    def gather(self, values: dict[int, Any]) -> list[Any]:
        """The values in partition order."""
        return [values[i] for i in range(len(self.actors))]


class DaskGroup(_CoordinatedGroup):
    """One Dask actor per partition, each on a worker process of its own."""

    def __init__(self, requests: Sequence[BuildRequest], **options: Any) -> None:
        """Connect (or start a local cluster) and start one actor per request."""
        distributed = require("distributed", "dask")
        self._owned: list[Any] = []
        self.client = self._connect(distributed, len(requests), options)
        addresses = sorted(self.client.scheduler_info()["workers"])
        futures = [
            self.client.submit(
                PartitionWorker,
                request,
                actor=True,
                workers=[addresses[i % len(addresses)]],
                pure=False,
            )
            for i, request in enumerate(requests)
        ]
        self.actors = [future.result() for future in futures]

    def _connect(self, distributed: Any, workers: int, options: dict) -> Any:
        """The client given, one to ``address``, or one to a new local cluster."""
        if options.get("client") is not None:
            return options["client"]
        if options.get("address") is not None:
            client = distributed.Client(options["address"])
            self._owned = [client]
            return client
        cluster = distributed.LocalCluster(
            n_workers=workers,
            threads_per_worker=1,
            processes=True,
            dashboard_address=None,
            host=LOCALHOST,
        )
        client = distributed.Client(cluster)
        self._owned = [client, cluster]
        return client

    def _call(self, actor: Any, method: str, args: tuple) -> Any:
        """Start the actor call; a Dask actor future."""
        return getattr(actor, method)(*args)

    def _wait(self, calls: list[Any]) -> list[Any]:
        """The results of the actor futures."""
        return [call.result() for call in calls]

    def close(self) -> None:
        """Drop the actors and close the client and cluster this group started."""
        self.actors = []
        for item in self._owned:
            item.close()
        self._owned = []


class RayGroup(_CoordinatedGroup):
    """One Ray actor per partition."""

    def __init__(self, requests: Sequence[BuildRequest], **options: Any) -> None:
        """Start Ray if needed, then one actor per request."""
        self.ray = require("ray", "ray")
        self.started = not self.ray.is_initialized()
        if self.started:
            self.ray.init(**options)
        remote = self.ray.remote(num_cpus=1)(PartitionWorker)
        self.actors = [remote.remote(request) for request in requests]

    def _call(self, actor: Any, method: str, args: tuple) -> Any:
        """Start the actor call; a Ray object reference."""
        return getattr(actor, method).remote(*args)

    def _wait(self, calls: list[Any]) -> list[Any]:
        """The results of the object references."""
        return self.ray.get(calls)

    def close(self) -> None:
        """Drop the actors, and shut Ray down when this group started it."""
        for actor in self.actors:
            self.ray.kill(actor)
        self.actors = []
        if self.started:
            self.ray.shutdown()
