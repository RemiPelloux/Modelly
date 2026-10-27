"""Time travel: rewind a run, replay it with changes, branch it, diff two runs.

``Recorder`` checkpoints a running model into a ring held in memory or on
disk; ``Recorder.at(step)`` returns a model at any recorded step, bit-identical
to a straight run; ``Recorder.branch`` returns several futures from one state;
``diff`` finds the first step, agent and attribute where two runs diverge.

``Timeline`` is the small interface tools such as a timeline scrubber use:
anything with ``steps``, ``span`` and ``at``. ``Recorder`` implements it.
"""

from typing import TYPE_CHECKING, Any, Protocol

from modelly.timetravel.diff import diff
from modelly.timetravel.recorder import Recorder
from modelly.timetravel.report import Difference, RunDiff
from modelly.timetravel.snapshot import agent_state, model_state

if TYPE_CHECKING:
    from modelly.core.model import Model


class Timeline(Protocol):
    """A recorded run a tool can list and scrub through."""

    @property
    def steps(self) -> list[float]:
        """The steps that hold a checkpoint, oldest first (instant to fetch)."""
        ...

    @property
    def span(self) -> tuple[float, float]:
        """The first and last step ``at`` accepts."""
        ...

    def at(self, step: float) -> "Model[Any, Any]":
        """A new, independent model in the state of the run at ``step``."""
        ...


__all__ = [
    "Difference",
    "Recorder",
    "RunDiff",
    "Timeline",
    "agent_state",
    "diff",
    "model_state",
]
