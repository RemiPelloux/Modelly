"""Recurring events: a Schedule describes when, an EventGenerator makes it happen."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import MethodType
from typing import TYPE_CHECKING, Any
from weakref import WeakMethod, ref

from modelly.time.events.event import Event, Priority, _create_callable_reference

if TYPE_CHECKING:
    from modelly.core.model import Model


@dataclass(frozen=True, slots=True)
class Schedule:
    """Defines when something should happen repeatedly.

    Attributes:
        interval: Time between executions (fixed value or callable returning value)
        start: Absolute time to begin (None = use current model time + interval)
        end: Absolute time to stop (None = no end)
        count: Maximum executions (None = unlimited)
    """

    interval: float | int | Callable[[Model], float | int] = 1.0
    start: float | None = None
    end: float | None = None
    count: int | None = None

    def __post_init__(self):
        """Validate schedule parameters."""
        if not callable(self.interval) and self.interval <= 0:
            raise ValueError(f"Schedule interval must be > 0, got {self.interval}")

        if self.count is not None and self.count <= 0:
            raise ValueError(
                f"Schedule count must be > 0 if provided, got {self.count}"
            )

        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError(
                f"Schedule start ({self.start}) cannot be after end ({self.end})"
            )


class EventGenerator:
    """A generator that creates recurring events based on a Schedule.

    Unlike a single Event, an EventGenerator is persistent and can be
    stopped or configured with stop conditions.

    Attributes:
        model: The model this generator belongs to
        function: The callable to execute for each generated event
        schedule: The Schedule defining when events occur
        priority: Priority level for generated events

    Notes:
        Event generators use a weak reference to the callable. Therefore, you cannot pass a lambda function in fn.
        A simulation event where the callable no longer exists (e.g., because the agent has been removed from the model)
        will fail silently. If you want to use functools.partial, please assign the partial function to a variable
        prior to creating the generator.

    """

    def __init__(
        self,
        model: Model,
        function: Callable[..., None],
        schedule: Schedule,
        priority: Priority = Priority.DEFAULT,
    ) -> None:
        """Initialize an EventGenerator.

        Args:
            model: The model this generator belongs to
            function: The callable to execute for each generated event.
                     Use functools.partial to bind arguments.
            schedule: The Schedule defining timing
            priority: Priority level for generated events
        """
        self.model = model
        self.function = _create_callable_reference(function)
        self.schedule = schedule
        self.priority = priority

        self._active: bool = False
        self._paused: bool = False
        self._current_event: Event | None = None
        self._execution_count: int = 0

    @property
    def is_active(self) -> bool:
        """Return whether the generator is currently active."""
        return self._active

    @property
    def execution_count(self) -> int:
        """Return the number of times this generator has executed."""
        return self._execution_count

    @property
    def next_scheduled_time(self) -> float | None:
        """Return the time of the next scheduled execution, or None if not scheduled."""
        if self._current_event is None:
            return None
        return self._current_event.time

    def _get_interval(self) -> float | int:
        """Get the next interval value."""
        if callable(self.schedule.interval):
            interval = self.schedule.interval(self.model)
            if interval <= 0:
                raise ValueError(f"Interval must be > 0, got {interval}")
            return interval
        return self.schedule.interval

    def _should_stop(self, next_time: float) -> bool:
        """Check if the generator should stop before scheduling the next event."""
        return (
            self.schedule.count is not None
            and self._execution_count >= self.schedule.count
        ) or (self.schedule.end is not None and next_time > self.schedule.end)

    def _execute_and_reschedule(self) -> None:
        """Execute the function and schedule the next event."""
        if not self._active or self._paused:
            return

        # Check the weakref at execution time, as Event does; a dead callback
        # stops the generator silently (no error raised).
        fn = self.function()
        if fn is None:
            self.stop()
            return

        firing_event = self._current_event
        fn()
        self._execution_count += 1

        # The callback may have stopped, paused, restarted, or resumed this
        # generator. Both start() and resume() schedule a new event and replace
        # _current_event, so in that case do not schedule a second one.
        if not self._active or self._paused or self._current_event is not firing_event:
            return

        next_time = self.model.time + self._get_interval()
        if not self._should_stop(next_time):
            self._schedule_next(next_time)
        else:
            self._finish()

    def _finish(self) -> None:
        """Deactivate after the last scheduled execution and leave the model."""
        self._active = False
        self._current_event = None
        self.model._event_generators.discard(self)

    def _schedule_next(self, time: float) -> None:
        """Schedule the next event at the given time."""
        self._current_event = Event(
            time,
            self._execute_and_reschedule,
            priority=self.priority,
        )
        self.model._event_list.add_event(self._current_event)

    def start(self) -> EventGenerator:
        """Start the event generator.

        Returns:
            Self for method chaining

        Raises:
            ValueError: If schedule.start is in the past, e.g. when restarting
                a stopped generator after its start time has passed.
        """
        if self._active:
            return self

        if self.schedule.start is not None and self.schedule.start < self.model.time:
            raise ValueError(
                f"Cannot start recurring schedule in the past. "
                f"Start time is {self.schedule.start}, current time is {self.model.time}"
            )

        if self.schedule.start is not None:
            start_time = self.schedule.start
        else:
            # Default: start at next interval from now
            start_time = self.model.time + self._get_interval()

        self._active = True
        self.model._event_generators.add(self)
        self._schedule_next(start_time)
        return self

    def stop(self) -> None:
        """Stop the event generator immediately."""
        self._active = False
        self._paused = False
        if self._current_event is not None:
            self._current_event.cancel()
            self._current_event = None
        self.model._event_generators.discard(self)

    def pause(self) -> None:
        """Pause the event generator temporarily.

        This cancels the currently scheduled event but keeps the generator
        active in the model. Execution can be resumed later using resume().
        """
        if not self._active or self._paused:
            return

        self._paused = True

        if self._current_event is not None:
            self._current_event.cancel()
            self._current_event = None

    def resume(self) -> None:
        """Resume a paused event generator."""
        if not self._active or not self._paused:
            return

        self._paused = False

        next_time = self.model.time + self._get_interval()

        if not self._should_stop(next_time):
            self._schedule_next(next_time)
        else:
            self._active = False
            self.model._event_generators.discard(self)

    def __getstate__(self) -> dict[str, Any]:
        """Prepare state for pickling."""
        state = self.__dict__.copy()
        fn = self.function() if self.function is not None else None
        state["_fn_strong"] = fn
        state["function"] = None
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore state after unpickling."""
        # Keep strong reference alive during entire method
        fn = state.pop("_fn_strong")

        # Update state first (keeps references alive)
        self.__dict__.update(state)

        # Now recreate weak reference
        if fn is not None:
            if isinstance(fn, MethodType):
                self.function = WeakMethod(fn)
            else:
                self.function = ref(fn)
        else:
            self.function = None
