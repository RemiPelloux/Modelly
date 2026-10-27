"""The profiler: time a running model's steps, agent-set loops, data collection and events.

``Profiler`` replaces a handful of framework methods while its ``with`` block
runs and puts the originals back on exit, so a model that is not being profiled
runs exactly the code it always does. The wrappers never draw a random number
nor reorder a loop: a profiled run gives the same results as an unprofiled one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from time import perf_counter
from typing import TYPE_CHECKING, Any

try:
    from time import thread_time
except ImportError:  # Pyodide: Emscripten has no per-thread CPU clock, one thread only
    from time import process_time as thread_time

from modelly.core.agentset import AgentSet, _HardKeyAgentSet
from modelly.data.collector import DataCollector
from modelly.profile.report import as_dataframe, as_dict, render_text
from modelly.time.events.event import Event
from modelly.time.events.generator import EventGenerator

if TYPE_CHECKING:
    import pandas as pd

    from modelly.core.model import Model

# The AgentSet methods that visit every member, timed on both set classes.
AGENT_SET_LOOPS = ("do", "shuffle_do", "map")
LOOPED_CLASSES = (_HardKeyAgentSet, AgentSet)
DEFAULT_TOP = 15
_MISSING = object()


@dataclass(slots=True)
class StepRecord:
    """What one profiled step cost.

    ``ops`` maps ``(kind, owner, name)`` to ``[calls, agents visited, wall s,
    CPU s]``. ``kind`` is an AgentSet method (``do``, ``shuffle_do``, ``map``),
    ``collect`` or ``event``; ``owner`` is the agent class (``A|B`` for a mixed
    set) or the collector class. Births and deaths count from this step's start
    to the next one's, so agents created by events in between are included.
    """

    step: int
    time: float
    agents: int
    wall: float = 0.0
    cpu: float = 0.0
    births: int = 0
    deaths: int = 0
    ops: dict[tuple[str, str, str], list] = field(default_factory=dict)

    def add(self, key: tuple[str, str, str] | None, agents: int, times: tuple) -> None:
        """Add one timed call; ``key`` None is the step itself."""
        wall, cpu = times
        if key is None:
            self.wall += wall
            self.cpu += cpu
            return
        entry = self.ops.get(key)
        if entry is None:
            self.ops[key] = [1, agents, wall, cpu]
            return
        entry[0] += 1
        entry[1] += agents
        entry[2] += wall
        entry[3] += cpu


def agent_classes(agentset: Any) -> str:
    """The class names of the members of ``agentset``, sorted and joined by ``|``."""
    return "|".join(sorted({type(agent).__name__ for agent in agentset})) or "(empty)"


def callable_name(fn: Any) -> str:
    """A readable name for a method name, a function or an event callback."""
    if isinstance(fn, str):
        return fn
    owner = getattr(fn, "__self__", None)
    if isinstance(owner, EventGenerator) and owner.function is not None:
        fn = owner.function() or fn
    return getattr(fn, "__qualname__", type(fn).__name__)


class Profiler:
    """Record where each step of ``model`` spends its time.

    Use it as a context manager around the run::

        with Profiler(model) as prof:
            model.run_for(100)
        print(prof.report())
        frame = prof.to_dataframe()

    Args:
        model: the model to profile.
        sample_every: profile one step in ``sample_every`` (steps 1, 1 + N, ...);
            the others run through the wrappers untimed.

    Notes:
        The patched methods are class attributes, so while the block runs every
        agent set, collector and event in the process is timed, not only those
        of ``model``. Only one profiler can be active at a time. Times of nested
        loops (an agent's step calling ``do`` on another set) are inclusive.
    """

    _active: Profiler | None = None

    def __init__(self, model: Model, sample_every: int = 1) -> None:
        """Prepare a profiler; nothing is patched until the ``with`` block starts."""
        if sample_every < 1:
            raise ValueError(f"sample_every must be at least 1, got {sample_every}")
        self.model = model
        self.sample_every = sample_every
        self.records: list[StepRecord] = []
        self._record: StepRecord | None = None
        self._steps_seen = 0
        self._born_mark = 0
        self._saved: list[tuple[type, str, Any]] = []

    def __enter__(self) -> Profiler:
        """Install the timing wrappers."""
        if Profiler._active is not None:
            raise RuntimeError("another Profiler is already active")
        Profiler._active = self
        for cls in LOOPED_CLASSES:
            for name in AGENT_SET_LOOPS:
                self._patch(cls, name, lambda f, n=name: self._wrap_loop(n, f))
        self._patch(DataCollector, "collect", self._wrap_collect)
        self._patch(Event, "execute", self._wrap_event)
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Restore every original method, also when the run raised."""
        try:
            self._close_record()
        finally:
            for owner, name, original in reversed(self._saved):
                if original is _MISSING:
                    delattr(owner, name)
                else:
                    setattr(owner, name, original)
            self._saved.clear()
            Profiler._active = None

    # --- results --------------------------------------------------------------

    def report(self, top: int = DEFAULT_TOP) -> str:
        """A text table of the ``top`` costliest operations, with hints."""
        return render_text(self, top)

    def to_dict(self) -> dict[str, Any]:
        """The summary, the per-step totals and the hints, JSON-ready."""
        return as_dict(self)

    def to_dataframe(self) -> pd.DataFrame:
        """One row per step (kind ``step``) and per operation within a step."""
        return as_dataframe(self)

    # --- patching -------------------------------------------------------------

    def _patch(self, owner: type, name: str, make: Callable) -> None:
        """Replace ``owner.name`` by ``make(original)`` and remember how to undo it."""
        self._saved.append((owner, name, owner.__dict__.get(name, _MISSING)))
        setattr(owner, name, make(getattr(owner, name)))

    def _timed(self, key: Any, agents: int, call: Callable, /, *args, **kwargs) -> Any:
        """Run ``call`` and add its wall and CPU time to the open record."""
        record = self._record
        wall, cpu = perf_counter(), thread_time()
        try:
            return call(*args, **kwargs)
        finally:
            record.add(key, agents, (perf_counter() - wall, thread_time() - cpu))

    def _wrap_loop(self, name: str, original: Callable) -> Callable:
        """Time ``AgentSet.<name>`` per agent class and method."""

        @wraps(original)
        def loop(agentset, method, *args, **kwargs):
            if self._record is None:
                return original(agentset, method, *args, **kwargs)
            key = (name, agent_classes(agentset), callable_name(method))
            return self._timed(
                key, len(agentset), original, agentset, method, *args, **kwargs
            )

        return loop

    def _wrap_collect(self, original: Callable) -> Callable:
        """Time ``DataCollector.collect``."""

        @wraps(original)
        def collect(collector, model):
            if self._record is None:
                return original(collector, model)
            key = ("collect", type(collector).__name__, "collect")
            return self._timed(key, 0, original, collector, model)

        return collect

    def _wrap_event(self, original: Callable) -> Callable:
        """Time the model's step event, and every other event as a callback."""
        driver = self.model._default_schedule

        @wraps(original)
        def execute(event):
            fn = event.fn() if event.fn is not None else None
            if getattr(fn, "__self__", None) is driver:
                self._open_record()
                if self._record is not None:
                    return self._timed(None, 0, original, event)
            if self._record is None or fn is None:
                return original(event)
            return self._timed(("event", "", callable_name(fn)), 0, original, event)

        return execute

    # --- records --------------------------------------------------------------

    def _open_record(self) -> None:
        """Close the running record and open one for this step if it is sampled."""
        self._close_record()
        index = self._steps_seen
        self._steps_seen += 1
        if index % self.sample_every:
            return
        model = self.model
        self._record = StepRecord(index + 1, model.time, len(model.agents))
        self._born_mark = model.agent_id_counter

    def _close_record(self) -> None:
        """Count births and deaths of the running record and store it."""
        record = self._record
        if record is None:
            return
        births = self.model.agent_id_counter - self._born_mark
        record.births = births
        record.deaths = births - (len(self.model.agents) - record.agents)
        self.records.append(record)
        self._record = None
