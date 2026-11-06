"""Recording the runs of a scenario sweep as an executor finishes them.

``run_scenarios`` submits the scenarios to an executor in chunks (one submission
costs the parent tens of microseconds, which adds up over many short runs); each
chunk returns one result per scenario, recorded in the store as it arrives, and
the progress bar advances per scenario.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable, Iterator, Mapping, Sequence
from concurrent.futures import BrokenExecutor, as_completed
from typing import TYPE_CHECKING, Any

from modelly.batch.runs import _chunk_size
from modelly.scenarios.exceptions import FailureInfo, FailureOrigin
from modelly.scenarios.store import RunId

if TYPE_CHECKING:
    from concurrent.futures import Executor, Future

    from modelly.scenarios.scenario import Scenario
    from modelly.scenarios.store import Reference, Store

Result = tuple["Reference", None] | tuple[None, FailureInfo]


def chunks(executor: Executor, scenarios: list[Scenario]) -> list[list[Scenario]]:
    """The scenarios in submission chunks: one per chunk unless the pool's size is known."""
    workers = getattr(executor, "_max_workers", None)
    size = _chunk_size(len(scenarios), workers) if isinstance(workers, int) else 1
    return [scenarios[i : i + size] for i in range(0, len(scenarios), size)]


def record(store: Store, scenario: Scenario, result: Result) -> None:
    """Mark the run of scenario as succeeded or failed in store."""
    ref, failure = result
    if failure is None:
        assert ref is not None  # a run without a failure has its output's reference
        store.mark_succeeded(ref)
    else:
        run_id = RunId(scenario.scenario_id, scenario.replication_id)
        store.mark_failed(run_id, failure)


def failure_info(
    origin: FailureOrigin, cause: BaseException, exc: BaseException
) -> FailureInfo:
    """Describe a failure from its cause, with the traceback of exc."""
    return FailureInfo(
        origin=origin,
        exception_type=type(cause).__name__,
        message=str(cause),
        traceback="".join(traceback.format_exception(exc)),
    )


def _results(
    futures: Mapping[Future[Any], Sequence[Scenario]],
) -> Iterator[tuple[Scenario, Result]]:
    """Each scenario with its result, chunk by chunk as the chunks complete."""
    for future in as_completed(futures):
        chunk = futures[future]
        try:
            results: Sequence[Result] = future.result()
        except BrokenExecutor:
            raise
        except Exception as e:
            # pickling failure or CancelledError on the return trip; record as failed and continue
            results = [(None, failure_info(FailureOrigin.WRITING, e, e))] * len(chunk)
        yield from zip(chunk, results)


def collect_futures(
    futures: Mapping[Future[Any], Sequence[Scenario]],
    store: Store,
    bar: Callable[..., Any],
) -> None:
    """Record each scenario's result as its chunk completes; a broken executor propagates."""
    for scenario, result in bar(_results(futures)):
        record(store, scenario, result)


def abort_pending(store: Store, error: BrokenExecutor) -> None:
    """Mark every run still pending in store as aborted by a broken executor."""
    cause = error.__cause__ or error
    for entry in list(store.pending()):
        store.mark_aborted(entry, failure_info(FailureOrigin.ABORTED, cause, error))
