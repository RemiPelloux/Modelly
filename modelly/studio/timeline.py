"""The run Studio's scrubber moves through: checkpoints when the model allows, else replay.

``track`` records a model with a ``modelly.timetravel.Recorder``: scrubbing restores a
checkpoint, instantly. A model that cannot be checkpointed (it holds a lambda, say) gets a
``ReplayTimeline`` instead: the same ``steps`` / ``span`` / ``at`` interface, where ``at``
rebuilds the model from the start of the run and runs it on to the step. Seeded runs are
reproducible, so the state is the same; it only takes longer.
"""

from __future__ import annotations

import pickle
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING

from modelly.core.exceptions import CheckpointError
from modelly.timetravel.recorder import Recorder, thaw

if TYPE_CHECKING:
    from modelly.core.model import Model
    from modelly.timetravel import Timeline

# What pickling a model that holds an unsaveable object raises: a lambda (CheckpointError),
# a generator or an iterator (TypeError), a local class (PicklingError, AttributeError).
CHECKPOINT_ERRORS = (CheckpointError, TypeError, pickle.PicklingError, AttributeError)


def reason(error: BaseException) -> str:
    """The first line of a checkpoint error, for the run log."""
    text = str(error).strip()
    return text.splitlines()[0] if text else type(error).__name__


class GuardedRecorder(Recorder):
    """A ``Recorder`` that stops, instead of raising, when the model cannot be saved.

    The step that hit the error completes; ``failed`` then holds the reason and the
    checkpoints taken so far stay available.
    """

    failed: str | None = None

    def _capture(self) -> None:
        """Checkpoint the model, or stop recording when it cannot be pickled."""
        if self.failed:
            return
        try:
            super()._capture()
        except CHECKPOINT_ERRORS as error:
            self.failed = reason(error)
            self.stop()


class ReplayTimeline:
    """A timeline for a model that cannot be checkpointed: ``at`` reruns from the start.

    Args:
        start: Returns a new model in the state the run started from.
        live: The model being run; the span ends at its current time.
    """

    def __init__(self, start: Callable[[], Model], live: Model) -> None:
        """Follow ``live``, which started as ``start()`` returns."""
        self.start = start
        self.live = live
        self.first = live.time

    @property
    def steps(self) -> list[float]:
        """Only the start of the run is held."""
        return [self.first]

    @property
    def span(self) -> tuple[float, float]:
        """From the start of the run to the live model's time."""
        return self.first, self.live.time

    def at(self, step: float) -> Model:
        """A new model at ``step``: the run rebuilt and run on to ``step``.

        Raises:
            ValueError: If ``step`` is outside ``span``.
        """
        first, last = self.span
        if not first <= step <= last:
            raise ValueError(f"Step {step} is outside the recorded span {self.span}.")
        model = self.start()
        if step > model.time:
            model.run_for(step - model.time)
        return thaw(model)

    def stop(self) -> None:
        """Nothing to stop: a replay timeline does not hook the model."""


def track(
    model: Model, start: Callable[[], Model], every: float, budget: int
) -> tuple[Timeline, str | None]:
    """Record ``model``: a ``Recorder`` when it can be checkpointed, else a replay.

    Returns:
        The timeline and, when it is a replay, the reason checkpoints were not possible.
    """
    recorder = GuardedRecorder(model, every=every, memory_budget=budget)
    recorder.start()
    if recorder.failed:
        return ReplayTimeline(start, model), recorder.failed
    return recorder, None


def fall_back(recorder: GuardedRecorder) -> ReplayTimeline:
    """The replay timeline that takes over when ``recorder`` failed mid-run."""
    first = recorder.steps[0]
    timeline = ReplayTimeline(partial(recorder.at, first), recorder.model)
    timeline.first = first
    return timeline


__all__ = ["ReplayTimeline", "track"]
