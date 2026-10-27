"""One browser tab's run: build, step, profile, record, scrub and replay a model.

``StudioSession`` holds no widget: the Solara app calls it and redraws from what it holds,
and the tests drive it directly. Every method that changes the run takes ``lock``, so the
play loop's thread and the widgets' callbacks never see a half-made step.
"""

from __future__ import annotations

import inspect
import threading
from collections import deque
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from modelly.lint import lint_paths
from modelly.profile.loader import build_model
from modelly.profile.profiler import DEFAULT_TOP, Profiler
from modelly.studio.params import parameters_of
from modelly.studio.recording import SessionRecording
from modelly.studio.timeline import ReplayTimeline, fall_back, track
from modelly.timetravel.recorder import reseed_model
from modelly.viz.render.portrayal import ClassColours

if TYPE_CHECKING:
    import modelly.lint
    from modelly.core.model import Model
    from modelly.studio.config import StudioConfig

LOG_LINES = 200
# The profiler patches classes process-wide: one session profiles at a time.
_PROFILER_LOCK = threading.Lock()


def _replayed(timeline, step: float, changes: dict, seed: int | None) -> Model:
    """The model ``timeline`` holds at ``step``, with ``changes`` applied, as replayed."""
    model = timeline.at(step)
    _apply(model, changes, seed)
    return model


def _apply(model: Model, changes: dict[str, Any], seed: int | None) -> None:
    """Set the changed scenario values on ``model`` and reseed it when ``seed`` is given."""
    for name, value in changes.items():
        setattr(model.scenario, name, value)
    if seed is not None:
        reseed_model(model, np.random.SeedSequence(seed))


class StudioSession:
    """The state of one Studio run, independent of the widgets that show it.

    Args:
        model_class: The model to run.
        config: The Studio settings.
        agent_portrayal: How the space view draws agents; one colour per class when None.
    """

    def __init__(
        self,
        model_class: type[Model],
        config: StudioConfig,
        agent_portrayal: Callable | None = None,
    ) -> None:
        """Build the first run with the default parameters and ``config.seed``."""
        self.model_class = model_class
        self.config = config
        self.parameters = parameters_of(model_class)
        self.values = {p.name: p.default for p in self.parameters if p.editable}
        self.seed = config.seed
        self.portrayal = agent_portrayal or ClassColours()
        self.lock = threading.RLock()
        self.log: deque[str] = deque(maxlen=LOG_LINES)
        self.records: deque = deque(maxlen=config.profile_steps)
        self.model: Model | None = None
        self.view: Model | None = None
        self.timeline = None
        self.recording = SessionRecording(config.target)
        # Posteriors and sensitivity results the Analysis tab shows, with their names.
        self.analyses: list[tuple[str, Any]] = []
        self.reset()

    # --- the run --------------------------------------------------------------

    @property
    def shown(self) -> Model:
        """The model the views show: the scrubbed-to state, else the live model."""
        return self.view if self.view is not None else self.model

    @property
    def replaying(self) -> bool:
        """Whether scrubbing reruns the model instead of restoring checkpoints."""
        return isinstance(self.timeline, ReplayTimeline)

    def say(self, message: str) -> None:
        """Add a line to the run log."""
        time = self.model.time if self.model is not None else 0
        self.log.append(f"[t={time:g}] {message}")

    def _build(self, values: dict[str, Any], seed: int) -> Model:
        """A new model with ``values`` and ``seed``."""
        return build_model(self.model_class, values, seed)

    def _start(self, model: Model, start: Callable[[], Model]) -> None:
        """Make ``model`` the live run, recorded from now on.

        ``start`` rebuilds the state the run starts from; it is kept only when the model
        cannot be checkpointed and scrubbing replays the run from there.
        """
        if self.timeline is not None:
            self.timeline.stop()
        self.model, self.view = model, None
        self._run_values, self._run_seed = dict(self.values), self.seed
        self.records.clear()
        self.timeline, reason = track(
            model, start, self.config.every, self.config.memory_budget
        )
        if reason:
            self.say(f"no checkpoints ({reason}); scrubbing replays the run instead")

    def reset(self) -> None:
        """Rebuild the model from the panel's values and seed, at step 0."""
        with self.lock:
            start = partial(self._build, dict(self.values), self.seed)
            model = start()
            self._start(model, start)
            self.recording.new_run(self.values, self.seed, model.time)
            self.say(f"new run, seed {self.seed}: {self.values}")

    def step(self, n: int = 1) -> int:
        """Advance the live model ``n`` steps (fewer if it stops); the steps taken."""
        with self.lock:
            self.view = None
            for done in range(n):
                if not self.model.running:
                    self.say(
                        f"the model stopped (running is False) after {done} step(s)"
                    )
                    return done
                self._step_once()
            return n

    def _step_once(self) -> None:
        """One step, profiled when no other session is profiling."""
        if _PROFILER_LOCK.acquire(blocking=False):
            try:
                with Profiler(self.model) as prof:
                    self.model.step()
                self.records.extend(prof.records)
            finally:
                _PROFILER_LOCK.release()
        else:
            self.model.step()
        failed = getattr(self.timeline, "failed", None)
        if failed:  # the model became unsaveable mid-run
            self.timeline = fall_back(self.timeline)
            self.say(f"checkpoints stopped ({failed}); scrubbing replays the run")

    # --- the timeline ---------------------------------------------------------

    def scrub(self, step: float) -> None:
        """Show the run at ``step``; at or past the live step, show the live model."""
        with self.lock:
            first, last = self.timeline.span
            if step >= last:
                self.view = None
                return
            self.view = self.timeline.at(max(step, first))

    def _changes(self, model: Model) -> dict[str, Any]:
        """The panel values changed since the run was built that ``model.scenario`` has."""
        changed = {k: v for k, v in self.values.items() if v != self._run_values.get(k)}
        skipped = sorted(k for k in changed if not hasattr(model.scenario, k))
        if skipped:
            self.say(f"not applied on replay (constructor arguments): {skipped}")
        return {k: v for k, v in changed.items() if k not in skipped}

    def replay(self) -> None:
        """Make the scrubbed-to state the live run, with the panel's changed values."""
        with self.lock:
            if self.view is None:
                return
            model, step = self.view, self.view.time
            changes = self._changes(model)
            seed = self.seed if self.seed != self._run_seed else None
            _apply(model, changes, seed)
            start = partial(_replayed, self.timeline, step, changes, seed)
            self._start(model, start)
            self.recording.replayed(step, changes, seed)
            self.say(f"replayed from step {step:g} with {changes or 'no changes'}")

    # --- the panels -----------------------------------------------------------

    def profile_report(self, top: int = DEFAULT_TOP) -> str:
        """The profiler's report over the last ``config.profile_steps`` steps."""
        with self.lock:
            prof = Profiler(self.model)
            prof.records = list(self.records)
            return prof.report(top=top)

    def source_file(self) -> Path | None:
        """The file the lint panel checks: the target's, else the class's source."""
        named = self.config.source_file
        if named is not None:
            return named
        found = inspect.getsourcefile(self.model_class)
        return Path(found) if found else None

    def lint(self) -> list[modelly.lint.Finding]:
        """The ``modelly lint`` findings of the model's file."""
        path = self.source_file()
        if path is None:
            return []
        try:
            return lint_paths([path])
        except (OSError, SyntaxError) as error:
            self.say(f"lint could not read {path}: {error}")
            return []
