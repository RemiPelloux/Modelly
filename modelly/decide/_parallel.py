"""Many runs of a decision study, in this process or over worker processes, in task order.

The decision and explanation tools call ``run(params, seed)`` (or another
function) many times. With ``workers=1`` (their default) the calls run here, one
after another, as a loop would; with more, :func:`modelly.batch.run_batch` spreads
them over processes and returns the results in task order, so every result and
seed is the one the loop gives. A function a fresh process cannot import (a
closure, such as ``model_runner``'s) runs in forked workers, on Linux only.
"""

from __future__ import annotations

import pickle
from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import Any

from modelly.batch.runs import run_batch


def _apply(job: tuple[Callable[[Any], Any], Any]) -> Any:
    """Call a job's function on its task (in a worker)."""
    function, task = job
    return function(task)


def _picklable(function: Callable[..., Any]) -> bool:
    """Whether ``function`` can be sent to a worker that starts clean."""
    try:
        pickle.dumps(function)
    except (pickle.PicklingError, AttributeError, TypeError):
        return False
    return True


def ordered(
    function: Callable[[Any], Any], tasks: Iterable[Any], workers: int | None = 1
) -> Iterator[Any]:
    """``function(task)`` for every task, in task order.

    With ``workers=1`` each call is made as the result is consumed, exactly as in a
    loop; otherwise every call runs first over ``workers`` processes (``None``:
    ``modelly.batch.default_workers()``).
    """
    if workers == 1:
        return map(function, tasks)
    tasks = list(tasks)
    if _picklable(function):
        return iter(run_batch(_apply, [(function, task) for task in tasks], workers))
    return iter(run_batch(function, tasks, workers))


class Call:
    """``run(params, seed)`` as a function of one ``(params, seed)`` task (picklable if run is)."""

    def __init__(self, run: Callable[[Mapping[str, Any], int], Any]) -> None:
        """Wrap ``run``."""
        self.run = run

    def __call__(self, task: tuple[Mapping[str, Any], int]) -> Any:
        """``run(params, seed)``."""
        params, seed = task
        return self.run(params, seed)


def runs(
    run: Callable[[Mapping[str, Any], int], Any],
    tasks: Iterable[tuple[Mapping[str, Any], int]],
    workers: int | None = 1,
) -> Iterator[Any]:
    """``run(params, seed)`` for every ``(params, seed)`` task, in task order."""
    return ordered(Call(run), tasks, workers)
