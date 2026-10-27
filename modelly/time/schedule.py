"""Event scheduling and time advance for :class:`modelly.core.model.Model`.

A mixin so the model file stays readable; every method here needs the
model's ``_event_list``, ``_event_generators``, ``time`` and signals.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable

from modelly.time.events.event import Event, Priority
from modelly.time.events.generator import EventGenerator, Schedule
from modelly.time.signals import ModelSignals, ObservableSignals, emit


class HasSchedule:
    """Scheduling, running and time advance, mixed into ``Model``."""

    def _set_time(self, value: float) -> None:
        """Set ``time`` and notify subscribers when it changes."""
        old = self.time
        self.time = value
        if old != value:
            self.notify("time", ObservableSignals.CHANGED, old=old, new=value)

    def _wrapped_step(self) -> None:
        """Advance time by one unit, processing any scheduled events."""
        self._advance_time(self.time + 1)

    def _advance_time(self, until: float) -> None:
        """Advance time to the given point, processing events along the way.

        Args:
            until: The time to advance to

        """
        if until <= self.time:
            warnings.warn(
                f"end time {until} is not larger than current time {self.time}",
                RuntimeWarning,
                stacklevel=2,
            )

            return
        # The heap hands out the next live event only if it is due, so a later
        # one stays where it is instead of being popped and pushed back.
        while (event := self._event_list._heap.pop_due(until)) is not None:
            self._set_time(event.time)
            event.execute()

        self._set_time(until)

    def schedule_event(
        self,
        function: Callable,
        *,
        at: float | None = None,
        after: float | None = None,
        priority: Priority = Priority.DEFAULT,
    ) -> Event:
        """Schedule a one-off event.

        Args:
            function: The callable to execute
            at: Absolute time to execute (mutually exclusive with after)
            after: Relative time from now to execute (mutually exclusive with at)
            priority: Priority level for the event

        Returns:
            The scheduled Event (can be used to cancel)

        Raises:
            ValueError: If both or neither of at/after are specified
            ValueError: If both or neither of at/after are specified, or if the scheduled time is in the past.
        """
        if (at is None) == (after is None):
            raise ValueError("Specify exactly one of 'at' or 'after'")

        time = at if at is not None else self.time + after
        # Enforce monotonic time progression
        if time < self.time:
            raise ValueError(
                f"Cannot schedule event in the past. "
                f"Scheduled time is {time}, but current time is {self.time}"
            )

        # The event holds its callback weakly: once this frame lets go of it, a
        # temporary callback is dead, and is refused. One weak reference is
        # built, the event's own (a WeakMethod costs about 0.5 us).
        event = Event(time, function, priority=priority)
        function = None
        if event.fn() is None:
            raise ValueError("function must be alive at Event creation.")

        self._event_list.add_event(event)
        return event

    def schedule_recurring(
        self,
        function: Callable,
        schedule: Schedule,
        priority: Priority = Priority.DEFAULT,
    ) -> EventGenerator:
        """Schedule a recurring event based on a Schedule.

        Args:
            function: The callable to execute repeatedly
            schedule: The Schedule defining when events occur
            priority: Priority level for generated events

        Returns:
            The EventGenerator (can be used to stop)

        Raises:
            ValueError: If the schedule start time is in the past.
        """
        generator = EventGenerator(self, function, schedule, priority)
        generator.start()
        return generator

    @emit("model", ModelSignals.RUN_ENDED, when="after")
    def run_for(self, duration: float | int) -> None:
        """Run the model for the specified duration.

        Args:
            duration: Time units to advance
        """
        self._advance_time(self.time + duration)

    @emit("model", ModelSignals.RUN_ENDED, when="after")
    def run_until(self, end_time: float | int) -> None:
        """Run the model until the specified time.

        Args:
            end_time: Absolute time to run until

        If model.time is larger than end_time, the method returns directly.

        """
        if self.time > end_time:
            warnings.warn(
                f"end_time {end_time} is not larger than current time {self.time}",
                RuntimeWarning,
                stacklevel=2,
            )
            return

        self._advance_time(end_time)
