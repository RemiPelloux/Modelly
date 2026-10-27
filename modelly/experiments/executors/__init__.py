"""Executors: where an experiment's runs execute, chosen by name.

=============  ============================================================
``serial``     in this process, one run after another
``threads``    a thread pool (parallel on free-threaded Python builds)
``processes``  a process pool started with ``forkserver`` or ``spawn``
``dask``       a ``dask.distributed`` cluster (a local one by default)
``ray``        a Ray cluster (``modelly-abm[ray]``)
``slurm``      a SLURM job array submitted with ``sbatch``
``pbs``        a PBS job array submitted with ``qsub``
=============  ============================================================

Every executor calls :func:`modelly.experiments.tasks.run_task` once per run
and yields its :class:`~modelly.experiments.tasks.RunOutcome`; the worker
writes the run's Parquet file itself, so the results never depend on the
executor. A plugin adds an executor through the ``modelly.executors`` entry
point group (``name = "package.module:ExecutorClass"``) or
:func:`register_executor`.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterator, Sequence
from importlib.metadata import entry_points
from typing import Any

from modelly.experiments.tasks import RunOutcome, RunTask, spawn_safe

ENTRY_POINT_GROUP = "modelly.executors"

# Built-in executors, imported on first use (dask and ray stay optional).
BUILTIN = {
    "serial": "modelly.experiments.executors.local:SerialExecutor",
    "threads": "modelly.experiments.executors.local:ThreadExecutor",
    "processes": "modelly.experiments.executors.local:ProcessExecutor",
    "dask": "modelly.experiments.executors.dask_executor:DaskExecutor",
    "ray": "modelly.experiments.executors.ray_executor:RayExecutor",
    "slurm": "modelly.experiments.executors.cluster:SlurmExecutor",
    "pbs": "modelly.experiments.executors.cluster:PBSExecutor",
}

_REGISTRY: dict[str, Callable[..., Executor]] = {}


class Executor:
    """Base class: ``run(tasks, max_parallel)`` yields one outcome per task.

    ``in_process`` executors share this interpreter, so they can run models
    and outputs a fresh process could not import (a notebook class, a lambda).
    """

    name = "executor"
    in_process = False

    def __init__(self, **options: Any) -> None:
        """Keep the executor's options; unknown ones are an error."""
        if options:
            raise TypeError(
                f"{self.name} executor takes no option(s) {sorted(options)}"
            )

    def run(
        self, tasks: Sequence[RunTask], max_parallel: int | None = None
    ) -> Iterator[RunOutcome]:
        """Run every task, yielding each outcome as it finishes."""
        raise NotImplementedError

    def check(self, tasks: Sequence[RunTask]) -> None:
        """Refuse tasks naming a model or output a worker process cannot import."""
        if self.in_process or not tasks:
            return
        task = tasks[0]
        refs = [task.model, *(s for s in task.outputs.values() if ":" in s)]
        bad = [ref for ref in refs if not spawn_safe(ref)]
        if bad:
            raise TypeError(
                f"the {self.name} executor starts fresh processes that cannot import "
                f"{bad}: define them at module level in an importable file, or use "
                "executor='threads' or 'serial'"
            )


def register_executor(name: str, factory: Callable[..., Executor]) -> None:
    """Make ``factory(**options)`` available as ``executor=name``."""
    _REGISTRY[name] = factory


def _load(ref: str) -> Callable[..., Executor]:
    """The class a ``module:name`` reference names."""
    module, _, attribute = ref.partition(":")
    factory: Callable[..., Executor] = getattr(
        importlib.import_module(module), attribute
    )
    return factory


def _factory(name: str) -> Callable[..., Executor]:
    """The registered, built-in or entry-point factory for ``name``."""
    if name in _REGISTRY:
        return _REGISTRY[name]
    if name in BUILTIN:
        return _load(BUILTIN[name])
    for point in entry_points(group=ENTRY_POINT_GROUP):
        if point.name == name:
            loaded: Callable[..., Executor] = point.load()
            return loaded
    raise ValueError(
        f"unknown executor {name!r}; available: {', '.join(available_executors())}"
    )


def get_executor(executor: str | Executor, **options: Any) -> Executor:
    """An executor instance from its name (with ``options``) or as given.

    Example:
        >>> get_executor("threads").name
        'threads'
    """
    if isinstance(executor, Executor):
        if options:
            raise TypeError("options go to the executor's constructor, not run()")
        return executor
    return _factory(executor)(**options)


def available_executors() -> list[str]:
    """Every executor name: built-in, registered and from entry points."""
    plugins = {point.name for point in entry_points(group=ENTRY_POINT_GROUP)}
    return sorted(set(BUILTIN) | set(_REGISTRY) | plugins)


__all__ = [
    "ENTRY_POINT_GROUP",
    "Executor",
    "available_executors",
    "get_executor",
    "register_executor",
]
