"""Single simulation events and their priorities.

- Priority: An enumeration defining event priority levels (HIGH, DEFAULT, LOW)
- Event: A class representing individual events with timing and execution details

Events hold a weak reference to their callable, so canceled or orphaned events do
not keep agents alive.
"""

from __future__ import annotations

import itertools
import types
from collections.abc import Callable
from enum import IntEnum
from types import MethodType
from typing import TYPE_CHECKING, Any
from weakref import ReferenceType, WeakMethod, ref

if TYPE_CHECKING:
    from modelly.time.events.event_list import EventList


def _create_callable_reference(
    function: Callable[..., None],
) -> ReferenceType[Any] | WeakMethod:
    """Validate and create a weak-reference wrapper for an event callback."""
    if not callable(function):
        raise TypeError("function must be a callable")

    if isinstance(function, types.FunctionType) and function.__name__ == "<lambda>":
        raise ValueError("function must be alive at Event creation.")

    if isinstance(function, MethodType):
        function_ref = WeakMethod(function)
    else:
        try:
            function_ref = ref(function)
        except TypeError as exc:
            raise TypeError("function must be weak referenceable") from exc

    return function_ref


class Priority(IntEnum):
    """Enumeration of priority levels."""

    LOW = 10
    DEFAULT = 5
    HIGH = 1


class Event:
    """A simulation event.

    The callable is wrapped using weakref, so there is no need to explicitly cancel event if e.g., an agent
    is removed from the simulation.

    Attributes:
        time (float): The simulation time of the event
        fn (Callable): The function to execute for this event
        priority (Priority): The priority of the event
        unique_id (int) the unique identifier of the event
        function_args list[Any]: Argument for the function
        function_kwargs dict[str, Any]: Keyword arguments for the function


    Notes:
        Simulation events use a weak reference to the callable.
        If the callback no longer exists at execution time (e.g., because an agent
        has been removed), execution will fail silently.
        Lambda callbacks are rejected at Event creation.

    """

    _ids = itertools.count()

    @property
    def CANCELED(self) -> bool:  # noqa: D102
        return self._canceled

    def __init__(
        self,
        time: int | float,
        function: Callable[..., None],
        priority: Priority = Priority.DEFAULT,
        function_args: list[Any] | None = None,
        function_kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Initialize a simulation event.

        Args:
            time: the instant of time of the simulation event
            function: the callable to invoke
            priority: the priority of the event
            function_args: arguments for callable
            function_kwargs: keyword arguments for the callable
        """
        super().__init__()
        self.time = time
        self.priority = priority.value
        self._canceled = False

        weak_ref_fn = _create_callable_reference(function)

        self.fn = weak_ref_fn

        self.unique_id = next(self._ids)
        self.function_args = function_args if function_args else []
        self.function_kwargs = function_kwargs if function_kwargs else {}

        # Set by EventList.add_event, so cancel() can update the list's count.
        self._owner: ReferenceType[EventList] | None = None

    def execute(self) -> None:
        """Execute this event."""
        if not self._canceled:
            fn = self.fn()
            if fn is not None:
                fn(*self.function_args, **self.function_kwargs)

    def cancel(self) -> None:
        """Cancel this event."""
        if self._canceled:
            return

        self._canceled = True
        self.fn = None
        self.function_args = []
        self.function_kwargs = {}

        if self._owner is not None:
            owner = self._owner()
            if owner is not None:
                owner._on_cancellation()

    def __lt__(self, other: Event) -> bool:
        """Define a total ordering for events to be used by the heapq."""
        if self.time != other.time:
            return self.time < other.time
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.unique_id < other.unique_id

    def __getstate__(self) -> dict[str, Any]:
        """Prepare state for pickling."""
        state = self.__dict__.copy()
        # Convert weak reference back to strong reference for pickling
        fn = self.fn() if self.fn is not None else None
        state["_fn_strong"] = fn
        state["fn"] = None  # Don't pickle the weak reference
        state["_owner"] = None  # Weak references cannot be pickled
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore state after unpickling."""
        fn = state.pop("_fn_strong")
        self.__dict__.update(state)
        self._owner = None
        # Recreate callable reference strategy.
        if fn is not None:
            self.fn = _create_callable_reference(fn)
        else:
            self.fn = None
