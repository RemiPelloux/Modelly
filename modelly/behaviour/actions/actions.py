"""modelly.behaviour.actions: Timed, interruptible actions for Modelly agents.

An Action represents something an agent does over time. It integrates with
Modelly's event scheduling system for precise timing and supports interruption
with progress tracking and optional resumption.

Actions are subclassable: override on_start(), on_complete(),
on_interrupt(), and on_fail() to define behavior. The agent-side API
lives on the HasActions mixin; when an action ends, the agent's
on_idle() hook fires, and decisions about what to do next -- chain
another action, resume an interrupted one -- belong there.

Example::

    class Sheep(HasActions, Agent):
        pass

    class Forage(Action):
        def __init__(self, sheep):
            super().__init__(sheep, duration=5.0)

        def on_complete(self):
            self.agent.energy += 30

        def on_interrupt(self, progress):
            self.agent.energy += 30 * progress

    sheep.start_action(Forage(sheep))
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from modelly.log import create_module_logger
from modelly.time import Priority

if TYPE_CHECKING:
    from modelly.behaviour.actions.action import Action
    from modelly.core.model import Model
    from modelly.time import Event

_modelly_logger = create_module_logger()


class HasActions:
    """Mixin that lets an agent perform Actions.

    An agent performs at most one action at a time, held in
    ``current_action``. Actions are started with start_action(),
    preempted through interrupt_for() under the should_interrupt()
    policy, and force-stopped with cancel_action(). Whenever an action
    ends and nothing replaces it, the on_idle() wake fires.

    Action instances require their agent to inherit from this mixin.
    """

    if TYPE_CHECKING:
        # Supplied by the Agent class this mixin is combined with.
        model: Model
        unique_id: int

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the action slot."""
        self.current_action: Action | None = None
        self._wake_event: Event | None = None
        self._wake_previous: Action | None = None
        self._last_wake_time: float = float("-inf")
        super().__init__(*args, **kwargs)

    def remove(self) -> None:
        """Remove the agent, abandoning its action and pending wake.

        If the agent is currently performing an action, the action's
        scheduled completion event is cancelled silently. The action's
        on_interrupt() callback is NOT fired, because the agent is being
        destroyed — not making a behavioral decision. The action moves
        to no defined end state; it is simply abandoned. A pending
        on_idle wake is cancelled as well: a removed agent never wakes.

        If your action holds external resources (e.g., a Resource slot,
        a reservation, a lock), override remove() and call
        self.cancel_action() before super().remove() to ensure
        on_interrupt() fires and cleanup logic runs:

            def remove(self):
                self.cancel_action()  # Fires on_interrupt for cleanup
                super().remove()

        Notes:
            This is a deliberate design choice. The default silent
            cleanup is safe and avoids callbacks touching agent state
            during teardown. Models that need cleanup should opt in
            explicitly.
        """
        if self.current_action is not None:
            self.current_action._cancel_event()  # Silent cleanup, no callback
            self.current_action = None

        if self._wake_event is not None:
            self._wake_event.cancel()
            self._wake_event = None
            self._wake_previous = None

        super().remove()

    def start_action(self, action: Action) -> Action:
        """Start performing an action.

        The action must be in PENDING or INTERRUPTED state and the agent
        must not be currently performing another action.

        If one of the action's start requirements does not hold, the action moves
        to FAILED instead of starting and the agent stays idle. Check
        action.has_failed rather than assuming the action is running.

        Args:
            action: The Action to perform. Must have been created with
                this agent as its agent.

        Returns:
            The started Action.

        Raises:
            ValueError: If the agent is already performing an action,
                or if the action doesn't belong to this agent.
        """
        if self.current_action is not None:
            raise ValueError(
                f"Agent {self.unique_id} is already performing an action "
                f"({self.current_action!r}). Use interrupt_for() or "
                f"cancel_action() first."
            )

        if action.agent is not self:
            raise ValueError(
                f"Action's agent (id={action.agent.unique_id}) does not match "
                f"this agent (id={self.unique_id})."
            )

        self.current_action = action
        action.start()

        # If the action completed instantly (duration=0), start() already
        # called _do_complete which cleared current_action via the Action.
        return action

    def should_interrupt(self, current: Action, incoming: Action) -> bool:
        """Decide whether an incoming action may preempt the current one.

        Consulted by interrupt_for() whenever the agent is busy, with both
        priorities already resolved. Override to encode preemption policy,
        e.g. comparing action names or agent state instead of priorities.

        Args:
            current: The action the agent is performing.
            incoming: The action that wants to replace it.

        Returns:
            True to attempt the interruption, False to refuse it.

        Notes:
            Returning True cannot override the interruptible flag; use
            cancel_action() to force. This hook decides policy, the flag
            stays a hard property of the action.
        """
        return current.interruptible and incoming.priority >= current.priority

    def interrupt_for(self, new_action: Action) -> bool:
        """Interrupt the current action and start a new one.

        If there is no current action, simply starts the new one. Otherwise
        should_interrupt(current, incoming) decides whether to preempt.

        Args:
            new_action: The Action to perform instead.

        Returns:
            True if the new action was started. False if should_interrupt
            refused, the current action is non-interruptible, or the new
            action failed its start requirements.

        Notes:
            The False cases differ in what they leave behind. A refusal
            changes nothing. A failed requirement does not roll the
            interruption back: the old action is already INTERRUPTED and
            the agent is left idle, since whether to resume it is the
            model's decision.
        """
        if self.current_action is not None:
            new_action._resolve_priority()
            if not self.should_interrupt(self.current_action, new_action):
                return False
            if not self.current_action.interrupt():
                return False
                # interrupt() already cleared current_action

        self.start_action(new_action)
        return not new_action.has_failed

    def cancel_action(self) -> bool:
        """Cancel the current action, ignoring interruptible flag.

        Calls on_interrupt with partial progress. Returns False only if
        there is no current action.

        Returns:
            True if an action was cancelled, False if idle.
        """
        if self.current_action is None:
            return False

        self.current_action.cancel()
        # cancel() already cleared current_action
        return True

    @property
    def is_busy(self) -> bool:
        """Whether the agent is currently performing an action."""
        return self.current_action is not None

    def on_idle(self, previous: Action | None) -> None:
        """Called when the agent's action has ended and nothing replaced it.

        Fires for every way an action can end -- completion, interruption,
        cancellation, failure -- as a zero-delay ``Priority.LOW`` event
        rather than synchronously, so every agent finishing at time t
        decides after all completions at t have run.

        Override it to choose what to do next, typically by starting or
        resuming an action. The default does nothing, and nothing is
        resumed automatically: an interrupted action stays interrupted
        unless this hook (or other model code) restarts it.

        Args:
            previous: The action that just ended, in its final state
                (COMPLETED, INTERRUPTED, or FAILED). None is reserved for
                wakes not caused by an action ending; no built-in trigger
                sends it today.

        Notes:
            At most one wake fires per agent per model time, so a
            zero-duration action started here cannot re-trigger the hook
            in the same instant; a wake dropped by this guard is logged
            at DEBUG level. The wake is skipped when the agent is
            busy again by the time the event runs -- interrupt_for()
            refills the slot synchronously, so no idle gap ever existed.
            If several actions end before the wake runs, they coalesce
            into one call and ``previous`` is the latest of them.
        """

    def _schedule_wake(self, previous: Action | None) -> None:
        """Queue the deferred on_idle event, coalescing repeats.

        Called by Action._release_agent whenever this agent's slot is
        cleared. If a wake is already pending, or one already fired at
        the current model time, no second event is queued -- only
        ``previous`` is brought up to date. A wake dropped by the
        once-per-time guard is logged at DEBUG level.
        """
        self._wake_previous = previous
        if self._wake_event is not None:
            return
        if self._last_wake_time == self.model.time:
            _modelly_logger.debug(
                f"suppressed repeat on_idle wake for agent {self.unique_id} "
                f"at time {self.model.time} (ending action: {previous!r})"
            )
            return
        self._wake_event = self.model.schedule_event(
            self._fire_wake, after=0.0, priority=Priority.LOW
        )

    def _fire_wake(self) -> None:
        """Run the pending wake: call on_idle if the agent is still free."""
        previous = self._wake_previous
        self._wake_event = None
        self._wake_previous = None
        if self.current_action is not None:
            return
        # Recorded only when on_idle actually runs, so a busy skip does not
        # suppress a later release at the same model time.
        self._last_wake_time = self.model.time
        self.on_idle(previous)
