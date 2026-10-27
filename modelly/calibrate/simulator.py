"""Run batches of parameter points through the experiment executors and read them back.

Calibration and sensitivity analysis both ask the same question many times:
"what does the model produce at these points?". A :class:`Simulator` answers
it with the machinery of :mod:`modelly.experiments`: one
:class:`~modelly.experiments.tasks.RunTask` per (point, replicate), run on any
executor, each writing its Parquet file to a store folder per batch.

Seeds follow the experiment discipline. A batch is named by a key of integers;
its runs use ``SeedSequence(entropy, spawn_key=(point, replicate))`` with the
entropy drawn from ``SeedSequence(seed, spawn_key=(SIMULATION, *key))``, or the
same entropy for every batch when the batch asks for common random numbers.
The numbers therefore never depend on the executor, the worker count or the
order of the runs, and a batch already in its folder is read, not rerun.
"""

from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from modelly._optional import require
from modelly.experiments.executors import Executor, get_executor
from modelly.experiments.store import ResultsStore
from modelly.experiments.tasks import FAILED, INT64_MAX, RunTask

DEFAULT_EXECUTOR = "serial"
PROCESSES = "processes"
KEY_SEPARATOR = "-"


class Stream(enum.IntEnum):
    """The first spawn-key element of each independent random stream."""

    SIMULATION = 1
    COMMON = 2
    PROPOSAL = 3
    PREDICTION = 4
    DESIGN = 5
    BOOTSTRAP = 6


class SimulationError(RuntimeError):
    """A run of a calibration or sensitivity batch raised."""


def entropy(seed: int, *key: int) -> int:
    """An integer drawn from ``SeedSequence(seed, spawn_key=key)``."""
    state = np.random.SeedSequence(seed, spawn_key=key).generate_state(1, np.uint64)
    return int(state[0]) & int(INT64_MAX)


def generator(seed: int, *key: int) -> np.random.Generator:
    """The numpy Generator of the stream ``key`` of ``seed``."""
    return np.random.default_rng(np.random.SeedSequence(seed, spawn_key=key))


@dataclass
class Execution:
    """Where runs execute: an executor name (or instance), its parallelism and options.

    Used as a context manager, ``"processes"`` keeps one pool of workers for
    every batch until the block ends (see :mod:`modelly.calibrate.pool`).
    """

    executor: Any = DEFAULT_EXECUTOR
    max_parallel: int | None = None
    options: Mapping[str, Any] = field(default_factory=dict)
    _pooled: Any = field(default=None, init=False, repr=False)

    def runner(self) -> Executor:
        """The executor to submit a batch to."""
        if self._pooled is not None:
            pooled: Executor = self._pooled
            return pooled
        return get_executor(self.executor, **dict(self.options))

    def __enter__(self) -> Execution:
        """Start sharing one process pool when the executor is ``"processes"``."""
        if self.executor == PROCESSES:
            from modelly.calibrate.pool import PooledProcessExecutor  # noqa: PLC0415

            self._pooled = PooledProcessExecutor(**dict(self.options))
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Stop the shared pool."""
        if self._pooled is not None:
            self._pooled.close()
            self._pooled = None


@dataclass(frozen=True)
class Batch:
    """Points to simulate under one key; ``common`` reuses the same seeds for every batch."""

    key: tuple[int, ...]
    points: Sequence[Mapping[str, Any]]
    common: bool = False


@dataclass
class Simulator:
    """A model, its outputs, steps and replicates, and the folder batches go to.

    ``run`` returns, for every point, ``{output: array[replicate, step]}`` with
    ``steps + 1`` columns (a run that stopped early repeats its last value).
    """

    model: str
    outputs: dict[str, str]
    steps: int
    replicates: int
    seed: int
    root: Path

    def tasks(self, batch: Batch) -> list[RunTask]:
        """One task per (point, replicate) of ``batch``."""
        stream = (Stream.COMMON,) if batch.common else (Stream.SIMULATION, *batch.key)
        common: dict[str, Any] = {
            "model": self.model,
            "steps": self.steps,
            "outputs": self.outputs,
        }
        common |= {
            "entropy": entropy(self.seed, *stream),
            "store": str(self.folder(batch)),
        }
        return [
            RunTask(params=dict(params), point=point, replicate=replicate, **common)
            for point, params in enumerate(batch.points)
            for replicate in range(self.replicates)
        ]

    def folder(self, batch: Batch) -> Path:
        """The store folder of ``batch``."""
        return self.root / KEY_SEPARATOR.join(str(int(part)) for part in batch.key)

    def run(self, batch: Batch, execution: Execution) -> list[dict[str, np.ndarray]]:
        """Simulate every point of ``batch`` not yet in its folder; read them all."""
        return self.run_many([batch], execution)[0]

    def run_many(
        self, batches: Sequence[Batch], execution: Execution
    ) -> list[list[dict[str, np.ndarray]]]:
        """Run several batches in one submission to the executor; read each back."""
        stores = [ResultsStore(self.folder(batch)) for batch in batches]
        pending: list[RunTask] = []
        for batch, store in zip(batches, stores):
            store.claim(self._fingerprint(batch))
            finished = store.finished()
            pending += [task for task in self.tasks(batch) if task.seed not in finished]
        for outcome in execution.runner().run(pending, execution.max_parallel):
            if outcome.status == FAILED:
                raise SimulationError(f"run {outcome.run_id} failed:\n{outcome.error}")
        return [
            self._read(store, self.tasks(batch), len(batch.points))
            for batch, store in zip(batches, stores)
        ]

    def _fingerprint(self, batch: Batch) -> dict[str, Any]:
        """What a batch folder holds; a folder holding anything else is refused."""
        points = [dict(point) for point in batch.points]
        return {
            "model": self.model,
            "steps": self.steps,
            "outputs": self.outputs,
            "seed": self.seed,
            "common": batch.common,
            "points": points,
        }

    def _read(
        self, store: ResultsStore, tasks: list[RunTask], count: int
    ) -> list[dict[str, np.ndarray]]:
        """Every point's series, replicates stacked, padded to ``steps + 1`` values."""
        parquet = require("pyarrow.parquet", "experiments")
        rows: list[dict[str, list[np.ndarray]]] = [
            {name: [] for name in self.outputs} for _ in range(count)
        ]
        for task in tasks:
            # ParquetFile.read is much faster than read_table on many small files.
            # Closed at once: Windows cannot delete a folder with an open file.
            with parquet.ParquetFile(store.run_path(task.seed)) as file:
                table = file.read(columns=list(self.outputs), use_threads=False)
            for name in self.outputs:
                values = table.column(name).to_numpy().astype(float)
                rows[task.point][name].append(self._pad(values))
        return [
            {name: np.vstack(series) for name, series in row.items()} for row in rows
        ]

    def _pad(self, values: np.ndarray) -> np.ndarray:
        """``values`` extended with its last value to ``steps + 1`` entries."""
        missing = self.steps + 1 - len(values)
        return (
            np.concatenate([values, np.repeat(values[-1:], missing)])
            if missing
            else values
        )
