"""Find where two runs diverge: first in their collected data, then in state.

``diff`` takes two runs given as models, recorders, ``DataCollector`` objects
or model-variable DataFrames (``get_model_vars_dataframe()``):

- collected data (both runs have a collector or a DataFrame): the first
  collection step at which a model reporter differs, or, from collectors, the
  first agent and reporter whose agent record differs;
- state (both runs are models or recorders): the first model scalar, agent or
  agent attribute that differs (see :mod:`modelly.timetravel.snapshot`). Two
  recorders are compared at their common checkpoints, then replayed one time
  unit at a time from the last matching one, so the state difference is at
  the first step where the runs diverge; two models are compared as they are.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from modelly.core.model import Model
from modelly.data import DataCollector
from modelly.timetravel.recorder import Recorder
from modelly.timetravel.report import Difference, RunDiff
from modelly.timetravel.snapshot import (
    first_state_difference,
    first_value_difference,
    model_state,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

Run = Model | Recorder | DataCollector | pd.DataFrame
Rows = list[tuple[float, dict[str, Any]]]
# Replay granularity between two checkpoints: one model step.
STEP = 1.0


def _final(run: Run) -> Model | None:
    """The model a run ends with, or None for collected data alone."""
    if isinstance(run, Recorder):
        return run.at(run.span[1])
    return run if isinstance(run, Model) else None


def _collected(run: Run) -> DataCollector | pd.DataFrame | None:
    """The collected data of a run, if it has any."""
    if isinstance(run, DataCollector | pd.DataFrame):
        return run
    model = _final(run)
    return getattr(model, "datacollector", None)


def _model_rows(data: DataCollector | pd.DataFrame) -> Rows:
    """``(step, {reporter: value})`` per collection."""
    if isinstance(data, pd.DataFrame):
        records = data.to_dict("records")
        return [(float(step), row) for step, row in zip(data.index, records)]
    names = list(data.model_vars)
    values = zip(*(data.model_vars[name] for name in names))
    return [
        (s, dict(zip(names, row))) for s, row in zip(data._collection_steps, values)
    ]


def _first_row_difference(a: Rows, b: Rows, **who: Any) -> Difference | None:
    """The first step at which two row lists differ."""
    for (step_a, row_a), (step_b, row_b) in zip(a, b):
        if step_a != step_b:
            return Difference(min(step_a, step_b), "collected at", step_a, step_b)
        found = first_value_difference(row_a, row_b, step_a, **who)
        if found is not None:
            return found
    if len(a) != len(b):
        step = (a if len(a) > len(b) else b)[min(len(a), len(b))][0]
        return Difference(step, "collections", len(a), len(b))
    return None


def _agent_rows(data: DataCollector, step: float) -> dict[int, dict[str, Any]]:
    """``{unique_id: {reporter: value}}`` of one agent collection."""
    names = list(data.agent_reporters)
    rows = data._agent_records.get(step, [])
    return {row[1]: dict(zip(names, row[2:])) for row in rows}


def _first_agent_record_difference(
    a: DataCollector, b: DataCollector
) -> Difference | None:
    """The first step, agent and reporter whose agent record differs."""
    for step in sorted(a._agent_records.keys() | b._agent_records.keys()):
        rows_a, rows_b = _agent_rows(a, step), _agent_rows(b, step)
        for uid in sorted(rows_a.keys() | rows_b.keys()):
            if uid not in rows_a or uid not in rows_b:
                return Difference(step, "recorded", uid in rows_a, uid in rows_b, uid)
            found = first_value_difference(rows_a[uid], rows_b[uid], step, agent=uid)
            if found is not None:
                return found
    return None


def _earliest(found: Iterable[Difference | None]) -> Difference | None:
    """The difference with the lowest step, the first one on a tie."""
    present = [d for d in found if d is not None]
    return min(present, key=lambda d: d.step, default=None)


def data_difference(a: Run, b: Run) -> Difference | None:
    """The first difference in the data two runs collected."""
    data_a, data_b = _collected(a), _collected(b)
    if data_a is None or data_b is None:
        return None
    model_vars = _first_row_difference(_model_rows(data_a), _model_rows(data_b))
    if isinstance(data_a, pd.DataFrame) or isinstance(data_b, pd.DataFrame):
        return model_vars
    return _earliest([model_vars, _first_agent_record_difference(data_a, data_b)])


def _compare(a: Model, b: Model) -> Difference | None:
    """The first state difference of two models, at the first one's time."""
    return first_state_difference(model_state(a), model_state(b), a.time)


def _walk(rec: Recorder, start: float, stop: float) -> Iterator[Model]:
    """The recorded run at each step from ``start`` up to before ``stop``.

    One model is replayed forward, restoring a checkpoint instead wherever
    the run has one, so changes recorded with ``checkpoint()`` are seen.
    """
    recorded = set(rec.steps)
    model = rec.at(start)
    yield model
    while model.time + STEP < stop:
        target = model.time + STEP
        if target in recorded:
            model = rec.at(target)
        else:
            model._advance_time(target)
        yield model


def _refine(a: Recorder, b: Recorder, start: float, found: Difference) -> Difference:
    """Compare both runs step by step from ``start`` up to ``found``."""
    for model_a, model_b in zip(
        _walk(a, start, found.step), _walk(b, start, found.step)
    ):
        earlier = _compare(model_a, model_b)
        if earlier is not None:
            return earlier
    return found


def _recorded_difference(a: Recorder, b: Recorder) -> Difference | None:
    """The first state difference of two recorded runs."""
    end = min(a.span[1], b.span[1])
    common = sorted(s for s in set(a.steps) & set(b.steps) if s < end)
    previous = None
    for step in [*common, end]:
        found = _compare(a.at(step), b.at(step))
        if found is not None:
            return found if previous is None else _refine(a, b, previous, found)
        previous = step
    return None


def state_difference(a: Run, b: Run) -> Difference | None:
    """The first difference in the state of two runs."""
    if isinstance(a, Recorder) and isinstance(b, Recorder):
        return _recorded_difference(a, b)
    model_a, model_b = _final(a), _final(b)
    if model_a is None or model_b is None:
        return None
    return _compare(model_a, model_b)


def diff(run_a: Run, run_b: Run) -> RunDiff:
    """Where two runs first diverge.

    Args:
        run_a: A model, a ``Recorder``, a ``DataCollector`` or a DataFrame of
            model variables.
        run_b: The run to compare it with, of any of the same kinds.

    Returns:
        A :class:`RunDiff`: ``str()`` of it is a readable report, and its
        ``data`` and ``state`` fields say step, agent and attribute.
    """
    for run in (run_a, run_b):
        if not isinstance(run, Model | Recorder | DataCollector | pd.DataFrame):
            raise TypeError(f"Cannot diff a {type(run).__name__}.")
    return RunDiff(data_difference(run_a, run_b), state_difference(run_a, run_b))
