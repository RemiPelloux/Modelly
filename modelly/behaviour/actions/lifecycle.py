"""Action lifecycle: states, subclass hooks and the internal state transitions.

``ActionLifecycle`` is the base of :class:`modelly.behaviour.actions.Action`.
It holds the progress properties, the overridable hooks (on_start,
on_resume, on_complete, on_interrupt, on_fail) and the private transitions
that every way of ending an action goes through.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from enum import IntEnum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modelly.behaviour.actions.actions import HasActions
    from modelly.core.agent import Agent
    from modelly.core.model import Model
    from modelly.time import Event


class ActionState(IntEnum):
    """Lifecycle state of an Action."""

    PENDING = auto()
    ACTIVE = auto()
    COMPLETED = auto()
    INTERRUPTED = auto()
    FAILED = auto()


def _as_predicates(
    spec: Callable[[Agent], bool] | Iterable[Callable[[Agent], bool]] | None,
) -> list[Callable[[Agent], bool]]:
    """Normalise a requirement spec into a list the action owns."""
    if spec is None:
        return []
    if callable(spec):
        return [spec]
    return list(spec)


class ActionLifecycle:
    """Progress, hooks and state transitions shared by every Action."""

    if TYPE_CHECKING:
        # Set by Action.__init__.
        agent: HasActions
        model: Model
        duration: float
        priority: float
        state: ActionState
        completion_requirements: list[Callable[[Agent], bool]]
        _progress: float
        _start_time: float
        _event: Event | None
        _priority_spec: float | Callable[[Agent], float]
        _priority_resolved: bool

    # --- Properties ---

    @property
    def progress(self) -> float:
        """Time fraction completed, 0.0 to 1.0.

        Computed live while the action is active. For interrupted or
        completed actions, returns the final progress value.
        """
        if (
            self.state is ActionState.ACTIVE
            and self.duration > 0
            and self._start_time >= 0
        ):
            elapsed_this_attempt = self.model.time - self._start_time
            return min(1.0, self._progress + elapsed_this_attempt / self.duration)
        return self._progress

    @property
    def remaining_time(self) -> float:
        """Time remaining until completion.

        Computed live while active. For interrupted actions, returns
        the time that would remain if resumed.
        """
        return self.duration * (1.0 - self.progress)

    @property
    def elapsed_time(self) -> float:
        """Total time spent on this action so far (across all attempts)."""
        return self.duration * self.progress

    @property
    def is_resumable(self) -> bool:
        """Whether this action can be resumed (interrupted, not completed)."""
        return self.state is ActionState.INTERRUPTED and self._progress < 1.0

    @property
    def has_failed(self) -> bool:
        """Whether a requirement did not hold, at start or at completion."""
        return self.state is ActionState.FAILED

    # --- Lifecycle methods (override in subclasses) ---

    def on_start(self) -> None:
        """Called when the action starts executing for the first time.

        Override for setup logic (e.g., logging, animation triggers,
        resource reservation). Not called on resume — see on_resume().
        """

    def on_resume(self) -> None:
        """Called when the action resumes after interruption.

        Override to handle resumption differently from first start
        (e.g., logging "resumed" instead of "started", skipping
        setup that shouldn't happen twice).

        Default implementation calls on_start().
        """
        self.on_start()

    def on_complete(self) -> None:
        """Called when the action finishes normally.

        Override to apply the action's full effect (e.g., gaining
        energy, completing a transaction).
        """

    def on_interrupt(self, progress: float) -> None:
        """Called when the action is interrupted before completion.

        Override to handle partial completion. The progress parameter
        is the raw time fraction (0.0 to 1.0), giving you full control
        over how partial work translates to partial effect.

        Args:
            progress: Fraction of duration completed (elapsed / duration).

        Notes:
            Also called by cancel(). If you need to distinguish
            interruption from cancellation, check self.interruptible:
            a non-interruptible action that receives on_interrupt was
            necessarily cancelled, not interrupted.
        """

    def on_fail(self) -> None:
        """Called when a requirement does not hold.

        Override to release anything the action
        reserved, or to record the attempt.

        Notes:
            Check self.progress to tell the two failures apart: it is 1.0
            when the action ran its full duration and only then found the
            requirement broken, and below 1.0 when the action never got to
            run this attempt.
        """

    # --- Internal ---

    def _freeze_progress(self) -> None:
        """Snapshot live progress into _progress for storage."""
        if self.duration > 0 and self._start_time >= 0:
            elapsed_this_attempt = self.model.time - self._start_time
            self._progress = min(
                1.0, self._progress + elapsed_this_attempt / self.duration
            )
        else:
            self._progress = 1.0

    def _cancel_event(self) -> None:
        """Cancel the scheduled completion event if it exists."""
        if self._event is not None:
            self._event.cancel()
            self._event = None

    def _release_agent(self) -> None:
        """Clear the agent's slot and schedule its idle wake.

        Completion, interruption, cancellation, and failure all funnel
        through here, so the wake contract has a single path. An action
        that never held the slot (started directly, without
        start_action()) wakes nobody. HasActions.remove() is the one end
        that does not come through here: it abandons the action, and a
        dying agent must not wake.
        """
        if self.agent.current_action is self:
            self.agent.current_action = None
            self.agent._schedule_wake(self)

    def _resolve_priority(self) -> None:
        """Resolve the priority spec against the agent, at most once.

        Called from start(), and from HasActions.interrupt_for before it consults
        should_interrupt, since the incoming action has not started yet and
        its priority would otherwise still read 0.0. A callable spec is
        called at most once either way.
        """
        if self._priority_resolved:
            return
        self.priority = (
            self._priority_spec(self.agent)
            if callable(self._priority_spec)
            else self._priority_spec
        )
        self._priority_resolved = True

    def _requirements_met(self, requirements: list[Callable[[Agent], bool]]) -> bool:
        """Whether every requirement in the given list holds right now."""
        return all(requirement(self.agent) for requirement in requirements)

    def _fail(self) -> None:
        """Move to FAILED, release the agent, and fire on_fail()."""
        self.state = ActionState.FAILED
        self._release_agent()
        self.on_fail()

    def _do_complete(self) -> None:
        """Handle normal completion. Called by the scheduled event."""
        if self.state is not ActionState.ACTIVE:
            return

        # Progress reaches 1.0 even if a requirement broke: the full duration
        # elapsed, only the effect is withheld.
        self._progress = 1.0
        self._event = None

        if not self._requirements_met(self.completion_requirements):
            self._fail()
            return

        self.state = ActionState.COMPLETED
        self._release_agent()
        self.on_complete()
