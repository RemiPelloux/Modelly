"""``Cluster``: build a partitionable model split across workers, and run it.

::

    from modelly.distributed import Cluster, partition

    with Cluster(backend="dask", workers=4) as cluster:
        model = cluster.build(Epidemic, scenario, partition=partition.grid_blocks(2, 2))
        model.run_for(365)
        cluster.collect().to_parquet("runs/epidemic.parquet")

Backends: ``"local"`` (every partition in this process, in turn), ``"mpi"``
(one partition per rank: run the script with ``mpirun -n <partitions>``),
``"dask"`` and ``"ray"`` (one actor per partition). Under MPI every rank runs
the same script and gets the same results; write files from
``cluster.is_root`` only.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

import pandas as pd

from modelly.distributed.checkpoints import load_class, read_index, write_index
from modelly.distributed.contract import Partitionable, PartitionError, plan_of
from modelly.distributed.groups import LocalGroup, MPIGroup
from modelly.distributed.reduce import frame_of
from modelly.distributed.worker import BuildRequest

PROTOCOL = pickle.HIGHEST_PROTOCOL
TIME = "time"


def open_group(backend: str, requests: list[BuildRequest], options: dict) -> Any:
    """The group of workers for ``backend``."""
    if backend == "local":
        return LocalGroup(requests)
    if backend == "mpi":
        return MPIGroup(requests, options.get("comm"))
    from modelly.distributed.remote import (  # noqa: PLC0415 - optional backends
        DaskGroup,
        RayGroup,
    )

    if backend == "dask":
        return DaskGroup(requests, **options)
    if backend == "ray":
        return RayGroup(requests, **options)
    raise ValueError(f"unknown backend {backend!r}: local, mpi, dask or ray")


class DistributedModel:
    """A model split across the workers of a group, stepped in lock step."""

    def __init__(self, group: Any, model_class: type, rows: list | None = None) -> None:
        """Run the model of ``group``; ``rows`` continue a restored run."""
        self.group = group
        self.model_class = model_class
        self.plan: Partitionable = plan_of(model_class)
        self.rows: list[dict[str, Any]] = list(rows or [])
        if not self.rows:
            self._record()

    @property
    def time(self) -> float:
        """The model time of the last step."""
        return self.rows[-1][TIME]

    @property
    def partitions(self) -> int:
        """The number of partitions."""
        return self.group.size

    def step(self) -> None:
        """One step: every phase, with its halo exchange and migration."""
        group = self.group
        group.invoke("begin_step")
        for i, phase in enumerate(self.plan.phases):
            if phase.radius > 0:
                ghosts = group.exchange(group.invoke("ghosts_for", i))
                group.deliver("accept_ghosts", ghosts)
            outboxes = group.invoke("act", i)
            if phase.moves:
                group.deliver("accept_migrants", group.exchange(outboxes))
        self._record()

    def run_for(self, steps: int) -> None:
        """Run ``steps`` steps."""
        for _ in range(int(steps)):
            self.step()

    def _record(self) -> None:
        """Reduce the reporters across partitions into one row."""
        reports = self.group.gather(self.group.invoke("report"))
        row: dict[str, Any] = {TIME: reports[0][0]}
        for name, reducer in self.plan.reporters.items():
            row[name] = reducer.combine([parts[name] for _, parts in reports])
        self.rows.append(row)

    def collect(self) -> pd.DataFrame:
        """One row per step (the build included): the time and every reporter."""
        return pd.DataFrame(self.rows)

    def info(self) -> list[tuple[int, int, int, bool]]:
        """Per partition: agents built and kept, id counter, own stream keys."""
        return self.group.gather(self.group.invoke("info"))

    def population(self) -> list[int]:
        """The number of agents in each partition."""
        return [entry[1] for entry in self.info()]

    def snapshot(self, attributes: tuple[str, ...] = ()) -> pd.DataFrame:
        """Every agent by stream key, with its location and ``attributes``."""
        parts = self.group.gather(self.group.invoke("snapshot", tuple(attributes)))
        return frame_of((row for part in parts for row in part), attributes)

    def states(self) -> list[tuple]:
        """The full state of every agent, in stream-key order (``reduce.states``)."""
        parts = self.group.gather(self.group.invoke("states"))
        return sorted(row for part in parts for row in part)

    def checkpoint(self, directory: str | Path) -> Path:
        """Write one file per partition and ``index.json`` into ``directory``."""
        files = self.group.gather(self.group.invoke("save", str(directory)))
        if self.group.is_root:
            write_index(Path(directory), self.model_class, self.rows, files)
        return Path(directory)


def _check_build(model: DistributedModel) -> None:
    """The workers built one population between them, keyed the same way.

    Every worker built the whole population and kept its part, or each built
    its own part; the second needs stream keys that do not come from
    ``unique_id``, since each worker numbers its agents its own way.

    Raises:
        PartitionError: when the builds differ and stream keys come from ``unique_id``.
    """
    built = model.info()
    same = len({(entry[0], entry[2]) for entry in built}) == 1
    if same and sum(entry[1] for entry in built) == built[0][0]:
        return
    if not all(entry[3] for entry in built):
        raise PartitionError(
            "the workers built different populations, and some agents key their "
            "streams on unique_id, which then depends on the partition: build the "
            "same agents everywhere, or override stream_key() (see owns())"
        )


class Cluster:
    """Workers for split runs, on one backend (see the module docstring).

    Args:
        backend: ``"local"``, ``"mpi"``, ``"dask"`` or ``"ray"``.
        workers: the number of workers; ``None`` takes the partition count.
        **options: backend options: ``comm`` (MPI), ``address`` or ``client``
            (Dask), ``ray.init`` arguments (Ray).
    """

    def __init__(self, backend: str = "local", workers: int | None = None, **options):
        """Keep the settings; workers start in ``build`` or ``restore``."""
        self.backend, self.workers, self.options = backend, workers, options
        self.model: DistributedModel | None = None
        self._group: Any = None

    @property
    def is_root(self) -> bool:
        """Whether this process writes shared files (always, except MPI ranks > 0)."""
        return True if self._group is None else self._group.is_root

    def _start(self, requests: list[BuildRequest]) -> Any:
        """Close the previous workers and start a group for ``requests``."""
        if self.workers is not None and self.workers != len(requests):
            raise ValueError(
                f"{self.workers} workers for {len(requests)} partitions: one worker "
                "runs one partition"
            )
        self.close()
        self._group = open_group(self.backend, requests, self.options)
        return self._group

    def build(
        self, model_class: type, scenario: Any, partition: Any
    ) -> DistributedModel:
        """Build ``model_class(scenario=scenario)`` split by ``partition``.

        Raises:
            PartitionError: when the model is not partitionable, with the reason.
        """
        plan_of(model_class)
        blob = pickle.dumps(scenario, protocol=PROTOCOL)
        requests = [
            BuildRequest(model_class, blob, partition, i)
            for i in range(partition.partitions)
        ]
        self.model = DistributedModel(self._start(requests), model_class)
        _check_build(self.model)
        return self.model

    def restore(self, directory: str | Path) -> DistributedModel:
        """Continue a run from ``DistributedModel.checkpoint(directory)``."""
        index = read_index(directory)
        model_class = load_class(index["model"])
        requests = [
            BuildRequest(
                None,
                None,
                None,
                entry["partition"],
                checkpoint=str(Path(directory) / entry["file"]),
                digest=entry["sha256"],
            )
            for entry in index["files"]
        ]
        self.model = DistributedModel(self._start(requests), model_class, index["rows"])
        return self.model

    def collect(self) -> pd.DataFrame:
        """The reporter rows of the last model built or restored."""
        if self.model is None:
            raise RuntimeError("build or restore a model before collecting")
        return self.model.collect()

    def close(self) -> None:
        """Stop the workers."""
        if self._group is not None:
            self._group.close()
            self._group = None

    def __enter__(self) -> Cluster:
        """Use the cluster as a context manager."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Stop the workers on leaving the block."""
        self.close()
