"""The workers of a split run and the way bytes travel between them.

A group calls the same worker method on every partition (``invoke`` with the
same arguments, ``deliver`` with one payload each), routes the outboxes the
workers return to the inboxes of their receivers (``exchange``), and gives every
process all the workers' values in partition order (``gather``).

``LocalGroup`` keeps every partition in this process and runs them one after
the other: no parallelism, the reference for the other backends and the
easiest to debug. ``MPIGroup`` is one partition per MPI rank (run the script
under ``mpirun -n <partitions>``); routing is one ``alltoall`` and an error on
any rank is raised on every rank instead of leaving the others waiting.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from modelly._optional import require
from modelly.distributed.contract import PartitionError
from modelly.distributed.worker import BuildRequest, PartitionWorker

Outboxes = dict[int, dict[int, bytes]]
ROOT = 0
EXTRA = "distributed"


def transpose(outboxes: Outboxes) -> Outboxes:
    """Turn ``{sender: {receiver: data}}`` into ``{receiver: {sender: data}}``."""
    inboxes: Outboxes = {worker: {} for worker in outboxes}
    for sender in sorted(outboxes):
        for receiver, data in outboxes[sender].items():
            inboxes[receiver][sender] = data
    return inboxes


class LocalGroup:
    """Every partition in this process, run in turn."""

    is_root = True

    def __init__(self, requests: Sequence[BuildRequest]) -> None:
        """Build one worker per request."""
        self.workers = [PartitionWorker(request) for request in requests]
        self.size = len(self.workers)

    def invoke(self, method: str, *args: Any) -> dict[int, Any]:
        """Call ``method(*args)`` on every worker."""
        return {i: getattr(w, method)(*args) for i, w in enumerate(self.workers)}

    def deliver(self, method: str, payloads: dict[int, Any]) -> dict[int, Any]:
        """Call ``method(payloads[i])`` on worker ``i``."""
        return {i: getattr(w, method)(payloads[i]) for i, w in enumerate(self.workers)}

    @staticmethod
    def exchange(outboxes: Outboxes) -> Outboxes:
        """Route every outbox to its receivers."""
        return transpose(outboxes)

    def gather(self, values: dict[int, Any]) -> list[Any]:
        """The values in partition order."""
        return [values[i] for i in range(self.size)]

    def invoke_exchange(self, method: str, *args: Any) -> Outboxes:
        """``exchange(invoke(method, *args))``: call, then route the outboxes."""
        return self.exchange(self.invoke(method, *args))

    def invoke_gather(self, method: str, *args: Any) -> list[Any]:
        """``gather(invoke(method, *args))``: call, then the values in partition order."""
        return self.gather(self.invoke(method, *args))

    def close(self) -> None:
        """Drop the workers."""
        self.workers = []


class MPIGroup:
    """One partition per MPI rank of ``comm`` (``COMM_WORLD`` by default)."""

    def __init__(self, requests: Sequence[BuildRequest], comm: Any = None) -> None:
        """Build this rank's worker; the number of ranks must equal the partitions."""
        if comm is None:
            comm = require("mpi4py.MPI", EXTRA).COMM_WORLD
        self.comm, self.rank, self.size = comm, comm.Get_rank(), comm.Get_size()
        self.is_root = self.rank == ROOT
        if self.size != len(requests):
            raise PartitionError(
                f"{len(requests)} partitions on {self.size} MPI ranks: run the script "
                f"with mpirun -n {len(requests)}"
            )
        self.worker = None
        self.worker = self._agreed(PartitionWorker, requests[self.rank])

    def _agreed(self, function: Any, *args: Any) -> Any:
        """``function(*args)`` here, raising on every rank if it failed on any."""
        result, failure = _attempt(function, args)
        reports = self.comm.allgather(_report(failure))
        _raise_any(failure, reports)
        return result

    def invoke(self, method: str, *args: Any) -> dict[int, Any]:
        """Call ``method(*args)`` on this rank's worker."""
        return {self.rank: self._agreed(getattr(self.worker, method), *args)}

    def deliver(self, method: str, payloads: dict[int, Any]) -> dict[int, Any]:
        """Call ``method`` on this rank's worker with its payload."""
        return self.invoke(method, payloads[self.rank])

    def exchange(self, outboxes: Outboxes) -> Outboxes:
        """Send each rank its part of this rank's outbox; receive everyone's."""
        mine = outboxes[self.rank]
        received = self.comm.alltoall([mine.get(q) for q in range(self.size)])
        inbox = {p: data for p, data in enumerate(received) if data is not None}
        return {self.rank: inbox}

    def gather(self, values: dict[int, Any]) -> list[Any]:
        """Every rank's value, in rank order, on every rank."""
        return self.comm.allgather(values[self.rank])

    def invoke_exchange(self, method: str, *args: Any) -> Outboxes:
        """Call ``method`` and route its outbox in one ``alltoall``, the status inside.

        Each part carries the sender's failure, if any, so every rank still learns of a
        failure on any rank and raises it, without a collective of its own.
        """
        outbox, failure = _attempt(getattr(self.worker, method), args)
        mine = {} if outbox is None else outbox
        parts = [(_report(failure), mine.get(q)) for q in range(self.size)]
        received = self.comm.alltoall(parts)
        _raise_any(failure, [report for report, _ in received])
        inbox = {p: data for p, (_, data) in enumerate(received) if data is not None}
        return {self.rank: inbox}

    def invoke_gather(self, method: str, *args: Any) -> list[Any]:
        """Call ``method`` and gather every rank's value in one ``allgather``, as above."""
        value, failure = _attempt(getattr(self.worker, method), args)
        parts = self.comm.allgather((_report(failure), value))
        _raise_any(failure, [report for report, _ in parts])
        return [part for _, part in parts]

    def close(self) -> None:
        """Drop this rank's worker (MPI itself stays initialised for the script)."""
        self.worker = None


def _attempt(function: Any, args: tuple[Any, ...]) -> tuple[Any, Exception | None]:
    """``(function(*args), None)``, or ``(None, error)`` when it raised."""
    try:
        return function(*args), None
    # Any error must reach the other ranks, or they would wait forever.
    except Exception as error:
        return None, error


def _report(failure: Exception | None) -> str | None:
    """What a rank tells the others of its failure: its repr, or None."""
    return None if failure is None else repr(failure)


def _raise_any(failure: Exception | None, reports: Sequence[str | None]) -> None:
    """Raise this rank's own failure, else the first other rank's; nothing if none."""
    if failure is not None:
        raise failure
    for rank, report in enumerate(reports):
        if report is not None:
            raise PartitionError(f"MPI rank {rank} failed: {report}")
