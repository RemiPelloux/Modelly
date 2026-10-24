"""The Action class: something an agent does over time.

Lifecycle states, hooks and internal transitions live in
``modelly.behaviour.actions.lifecycle``; the agent-side API is the
HasActions mixin in ``modelly.behaviour.actions.actions``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from modelly.behaviour.actions.actions import HasActions
from modelly.behaviour.actions.lifecycle import (
    ActionLifecycle,
    ActionState,
    _as_predicates,
)

if TYPE_CHECKING:
    from modelly.core.agent import Agent
    from modelly.time import Event


def _not_action_agent(agent: Agent) -> TypeError:
    """Build the error raised when an agent lacks the HasActions mixin."""
    return TypeError(
        f"Action requires an agent with action support; make "
        f"{type(agent).__name__} inherit from "
        f"modelly.behaviour.actions.HasActions."
    )


class Action(ActionLifecycle):
    """Something an agent does over time.

    Actions have a duration, can be interrupted, and track their own
    lifecycle state. They integrate with Modelly's event scheduler for
    completion timing.

    Subclass and override on_start/on_complete/on_interrupt for complex
    behavior. All hooks default to doing nothing (pass).

    Attributes:
        agent: The agent performing this action.
        model: The model (shortcut for agent.model).
        name: Human-readable identifier. Defaults to the class name.
        duration: Time to complete. May be a callable(agent) -> float
            for state-dependent duration, resolved at start time.
        priority: Importance level. Higher = more important. May be a
            callable(agent) -> float, resolved once: at start, or earlier
            if HasActions.interrupt_for weighs it against a running action.
        interruptible: Whether higher-priority actions can preempt this.
        start_requirements: Predicates that must hold for the action to start.
        completion_requirements: Predicates that must hold for the effect to
            apply. Empty by default.
        state: Current lifecycle state (PENDING, ACTIVE, COMPLETED,
            INTERRUPTED, FAILED).
        progress: Time fraction completed, 0.0 to 1.0. Computed live
            while the action is active.

    Notes:
        Actions hold a reference to their agent, mirroring how agents
        reference their model. This allows actions to query and modify
        agent state directly in their hooks.
    """

    def __init__(
        self,
        agent: Agent,
        duration: float | Callable[[Agent], float] = 1.0,
        *,
        name: str | None = None,
        priority: float | Callable[[Agent], float] = 0.0,
        interruptible: bool = True,
        start_requirements: Callable[[Agent], bool]
        | Iterable[Callable[[Agent], bool]]
        | None = None,
        completion_requirements: Callable[[Agent], bool]
        | Iterable[Callable[[Agent], bool]]
        | None = None,
    ) -> None:
        """Initialize an Action.

        Args:
            agent: The agent that will perform this action.
            duration: Time to complete. Either a float or a callable
                that receives the agent and returns a float. Resolved
                when start() is called.
            name: Human-readable name. Defaults to the class name.
            priority: Importance level for interruption decisions. Either
                a float or a callable that receives the agent and returns
                a float. Resolved once, at start() or when interrupt_for
                first consults the agent's should_interrupt with it.
            interruptible: If False, interrupt() will fail and return False.
            start_requirements: A single callable(agent) -> bool, or an
                iterable of them. All must hold for the action to start.
            completion_requirements: The same, checked instead when the action
                completes, gating the effect rather than the attempt.

        Raises:
            TypeError: If the agent does not inherit from HasActions.
        """
        if not isinstance(agent, HasActions):
            raise _not_action_agent(agent)
        self.agent = agent
        self.model = agent.model
        self.interruptible = interruptible
        self._name: str | None = name
        self.start_requirements = _as_predicates(start_requirements)
        self.completion_requirements = _as_predicates(completion_requirements)

        # Store raw values (may be callables, resolved at start)
        self._duration_spec = duration
        self._priority_spec = priority

        # Resolved values (set in start(); priority possibly earlier, see
        # _resolve_priority)
        self.duration: float = 0.0
        self.priority: float = 0.0
        self._priority_resolved: bool = False

        # Lifecycle state
        self.state: ActionState = ActionState.PENDING
        self._progress: float = 0.0
        self._start_time: float = -1.0
        self._event: Event | None = None

    @property
    def name(self) -> str:
        """Human-readable name. Returns the class name by default.

        Can be set via __init__(name=...), per-instance assignment
        (``action.name = "dig"``), or overridden in subclasses.
        """
        return self._name if self._name is not None else self.__class__.__name__

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    # --- Execution (called by Agent, not typically by users) ---

    def start(self) -> Action:
        """Start executing this action (or resume from interruption).

        On first start (PENDING): resolves callable duration/priority,
        starts from progress=0. On resume (INTERRUPTED): continues from
        existing progress with remaining duration.

        If a requirement does not hold the action moves to FAILED instead,
        firing on_fail() rather than on_start() or on_resume(). Inspect
        state after starting rather than assuming the action is ACTIVE.

        Returns:
            Self, for chaining.

        Raises:
            ValueError: If the action is not in PENDING or INTERRUPTED state.
                A FAILED action cannot be restarted; create a new one.
        """
        resuming = self.state is ActionState.INTERRUPTED
        self._check_startable()

        # Gate entry before duration and priority are resolved, so a failing
        # action neither fires on_start() nor schedules a completion event.
        if not self._requirements_met(self.start_requirements):
            self._fail()
            return self

        # Resolve callables on first start only
        if not resuming:
            self._resolve_specs()

        self._start_time = self.model.time
        self.state = ActionState.ACTIVE

        if resuming:
            self.on_resume()
        else:
            self.on_start()

        self._schedule_completion()
        return self

    def interrupt(self) -> bool:
        """Interrupt this action.

        Updates progress, fires on_interrupt with the time fraction,
        and cancels the scheduled completion event. The action moves
        to INTERRUPTED state and can be resumed later with start().

        Returns:
            True if the action was interrupted, False if it could not
            be interrupted (non-interruptible or not active).
        """
        if self.state is not ActionState.ACTIVE:
            return False

        if not self.interruptible:
            return False

        self._freeze_progress()
        self._cancel_event()

        self.state = ActionState.INTERRUPTED
        self._release_agent()
        self.on_interrupt(self._progress)
        return True

    def cancel(self) -> bool:
        """Cancel this action, ignoring the interruptible flag.

        Like interrupt(), but always succeeds for active actions and
        moves to INTERRUPTED state. The action can still be resumed
        if desired.

        Returns:
            True if the action was cancelled, False if not active.
        """
        if self.state is not ActionState.ACTIVE:
            return False

        self._freeze_progress()
        self._cancel_event()

        self.state = ActionState.INTERRUPTED
        self._release_agent()
        self.on_interrupt(self._progress)
        return True

    def _check_startable(self) -> None:
        """Raise ValueError unless the action is PENDING or INTERRUPTED."""
        if self.state not in (ActionState.PENDING, ActionState.INTERRUPTED):
            raise ValueError(
                f"Cannot start action in {self.state.name} state. "
                f"Only PENDING or INTERRUPTED actions can be started."
            )

    def _resolve_specs(self) -> None:
        """Resolve the duration and priority specs on first start."""
        self.duration = (
            self._duration_spec(self.agent)
            if callable(self._duration_spec)
            else self._duration_spec
        )
        self._resolve_priority()

        if self.duration < 0:
            raise ValueError(f"Action duration must be >= 0, got {self.duration}")

    def _schedule_completion(self) -> None:
        """Complete now if no time remains, else schedule the completion event."""
        # Calculate remaining time
        remaining = self.duration * (1.0 - self._progress)

        # Instantaneous actions (or fully completed) complete immediately
        if remaining <= 0:
            self._do_complete()
            return

        # Schedule completion event for remaining duration
        self._event = self.model.schedule_event(self._do_complete, after=remaining)

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"{self.name}(state={self.state.name}, "
            f"progress={self.progress:.0%}, "
            f"duration={self.duration})"
        )
