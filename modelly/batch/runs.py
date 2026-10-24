"""Run many independent model runs in parallel, results in a deterministic order.

An experiment is usually a loop over parameter combinations and replicates,
each run depending only on its own parameters and seed. ``run_batch`` spreads
those calls over processes and returns the results in task order, so the output
(a CSV, a DataFrame) is identical to the sequential loop's, row for row.
``run_grid`` builds the factorial design, gives every run its own seed and
returns a DataFrame.

A function defined at module level in an importable file runs in workers that
start clean (``forkserver``, or ``spawn``). A function defined in a notebook, a
lambda or a closure cannot be imported by a fresh process; on Linux its workers
are forked instead and inherit it. Forking a process with threads (numpy's BLAS
pool, for one) can deadlock the child; it is rare in practice, so the warning
Python raises for it is silenced for these forks, and an importable function
avoids it. As with any multiprocessing
code on macOS and Windows, a script that calls ``run_batch`` needs the usual
``if __name__ == "__main__":`` guard, because the workers re-import it.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import pickle
import sys
import warnings
from collections.abc import Callable, Iterable, Mapping, Sequence
from itertools import product
from typing import Any

import numpy as np
import pandas as pd

WORKERS_ENV = "MODELLY_WORKERS"
DEFAULT_MAX_WORKERS = 8

_CAN_FORK = sys.platform.startswith("linux") and "fork" in mp.get_all_start_methods()
# Importable functions go to workers that start clean (no inherited threads).
_SAFE_START = "forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn"
# The DeprecationWarning os.fork() raises when the parent has threads (3.12+).
_FORK_WARNING = (
    r"This process .*is multi-threaded, use of fork\(\) may lead to deadlocks"
)

# The function of the batch being run, inherited by forked workers.
_CURRENT: Callable[[Any], Any] | None = None
_TASKS: list[Any] = []


def default_workers() -> int:
    """``MODELLY_WORKERS`` if set, else the number of CPUs, at most eight."""
    configured = os.environ.get(WORKERS_ENV)
    if configured:
        return max(1, int(configured))
    return max(1, min(DEFAULT_MAX_WORKERS, os.cpu_count() or 1))


def _call_by_index(index: int) -> Any:
    """Run task ``index`` of the batch the forked worker inherited."""
    return _CURRENT(_TASKS[index])


def run_batch(
    run: Callable[[Any], Any], tasks: Iterable[Any], workers: int | None = None
) -> list[Any]:
    """Call ``run(task)`` for every task; return the results in task order.

    Args:
        run: the function computing one run's result.
        tasks: one argument per run (parameters, seed, ...).
        workers: processes to use; ``None`` means ``default_workers()``, 1 runs
            inline in this process.

    An exception raised by a run propagates, as in the sequential loop.
    """
    global _CURRENT, _TASKS  # handed to forked workers
    tasks = list(tasks)
    workers = default_workers() if workers is None else workers
    if workers <= 1 or len(tasks) <= 1:
        return [run(task) for task in tasks]
    if _importable(run):
        with mp.get_context(_SAFE_START).Pool(workers) as pool:
            return pool.map(run, tasks, chunksize=1)
    if not _CAN_FORK:
        raise TypeError(
            f"{run!r} cannot be sent to worker processes on this platform: define it "
            "at module level in an importable file, or pass workers=1."
        )
    _CURRENT, _TASKS = run, tasks
    try:
        with warnings.catch_warnings():
            # Forking is the documented trade-off for closures (see the module
            # docstring), so silence CPython's fork warning for these forks only.
            warnings.filterwarnings("ignore", _FORK_WARNING, DeprecationWarning)
            pool = mp.get_context("fork").Pool(workers)
        with pool:
            return pool.map(_call_by_index, range(len(tasks)), chunksize=1)
    finally:
        _CURRENT, _TASKS = None, []


def _importable(run: Callable[[Any], Any]) -> bool:
    """Whether a fresh worker process can import ``run`` by its qualified name."""
    module = getattr(run, "__module__", None)
    if module in (None, "__main__") or "<" in getattr(run, "__qualname__", "<"):
        return False
    try:
        pickle.dumps(run)
    except (pickle.PicklingError, AttributeError, TypeError):
        return False
    return True


def grid_tasks(
    grid: Mapping[str, Sequence[Any]], replicates: int = 1, seed: int = 0
) -> list[dict[str, Any]]:
    """Every combination of ``grid`` times ``replicates``, each with its own seed.

    Seeds come from ``numpy.random.SeedSequence(seed).spawn``: independent
    streams, the same for a given design whatever the number of workers.
    """
    names = list(grid)
    combos = [dict(zip(names, values)) for values in product(*grid.values())]
    tasks = [
        {**combo, "replicate": rep} for combo in combos for rep in range(replicates)
    ]
    children = np.random.SeedSequence(seed).spawn(len(tasks))
    for task, child in zip(tasks, children):
        task["seed"] = int(child.generate_state(1, dtype=np.uint32)[0])
    return tasks


def run_grid(
    run: Callable[[dict[str, Any]], Mapping[str, Any]],
    grid: Mapping[str, Sequence[Any]],
    replicates: int = 1,
    seed: int = 0,
    workers: int | None = None,
) -> pd.DataFrame:
    """Run a factorial design in parallel; one DataFrame row per run.

    ``run`` receives a dict with the grid's parameters, ``replicate`` and
    ``seed``, and returns a mapping of outcome names to values. The row is the
    task followed by the outcomes, in design order.
    """
    tasks = grid_tasks(grid, replicates, seed)
    results = run_batch(run, tasks, workers)
    return pd.DataFrame(
        [{**task, **dict(result)} for task, result in zip(tasks, results)]
    )
