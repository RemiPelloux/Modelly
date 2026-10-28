"""The event list: a heap-based priority queue of simulation events.

Events are kept in chronological order, respecting priorities. Cancellation is
lazy, so the heap invariant is never broken, and the heap compacts itself once
canceled events dominate it. The heap itself is ``modelly._native.events.EventHeap``:
compiled when available, with an identical pure-Python twin.
"""

from __future__ import annotations

from heapq import nsmallest
from typing import TYPE_CHECKING, Any
from weakref import ReferenceType, ref

from modelly._native.events import EventHeap

if TYPE_CHECKING:
    from modelly.time.events.event import Event


class EventList:
    """An event list.

    This is a heap queue sorted list of events. Events are always removed from the left, so a binary heap is a
    performant and appropriate data structure. Events are sorted based on their time stamp, their priority, and
    their unique_id as a tie-breaker, guaranteeing a complete ordering.

    Canceling an event leaves it on the heap so the heap invariant is not broken.
    Models that repeatedly cancel and reschedule an event would therefore grow the
    heap without bound, so the list counts the canceled events it holds and rebuilds
    itself once they dominate. That count also makes len() an O(1) operation.

    Attributes:
        COMPACTION_RATIO (float): Fraction of canceled events above which the heap is
            rebuilt, which also bounds the peak heap at L / (1 - COMPACTION_RATIO)

    Notes:
        An event belongs to one event list at a time. Adding the same event to a
        second list hands ownership over, and the first list's count goes stale.
        An event's time and priority must not change while it is on a list.

    """

    COMPACTION_RATIO: float = 0.25

    def __init__(self):
        """Initialize an event list."""
        self._heap = EventHeap()
        # Built once and handed to every event, since creating it per push is costly.
        self._self_ref: ReferenceType[EventList] = ref(self)

    @property
    def _events(self) -> list[Event]:
        """The events on the heap, canceled ones included, in heap order (a copy)."""
        return self._heap.events()

    @property
    def _n_canceled(self) -> int:
        """The number of canceled events still on the heap."""
        return self._heap.canceled

    def __getstate__(self) -> dict[str, Any]:
        """Prepare state for pickling: the events in heap order, whichever heap holds them."""
        state = self.__dict__.copy()
        heap = state.pop("_heap")
        state["_events"] = heap.events()
        state["_n_canceled"] = heap.canceled
        state["_self_ref"] = None  # Weak references cannot be pickled
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore state after unpickling.

        Events drop their weak reference to this list when pickled, so it has to
        be re-established or later cancellations would go uncounted.
        """
        state = dict(state)
        self._heap = EventHeap(state.pop("_events"))
        self._heap.canceled = state.pop("_n_canceled")
        self.__dict__.update(state)
        self._self_ref = ref(self)
        for event in self._heap.events():
            event._owner = self._self_ref

    def add_event(self, event: Event):
        """Add the event to the event list.

        Args:
            event (Event): The event to be added

        Raises:
            ValueError: If the event has already been canceled. Cancellation is
                terminal, so such an event could never execute.

        """
        if event.CANCELED:
            raise ValueError(
                "Cannot add a canceled event to an event list. Cancellation is "
                "terminal, so the event would never execute."
            )

        event._owner = self._self_ref
        self._heap.push(event)

    def _on_cancellation(self) -> None:
        """Record a canceled event, compacting the heap once they dominate it.

        Only cancellation raises the share of canceled events, since adding an
        event grows the heap and popping one discards a tombstone. So this is
        the single place where compaction can become worthwhile.
        """
        heap = self._heap
        heap.canceled += 1

        if heap.canceled > len(heap) * self.COMPACTION_RATIO:
            self.compact()

    def peek_ahead(self, n: int = 1) -> list[Event]:
        """Look at the first n non-canceled event in the event list.

        Args:
            n (int): The number of events to look ahead

        Returns:
            list[Event]

        Raises:
            IndexError: If the eventlist is empty

        Notes:
            this method can return a list shorted then n if the number of non-canceled events on the event list
            is less than n.

        """
        # look n events ahead
        if self.is_empty():
            raise IndexError("event list is empty")

        # Filter out canceled events and get n smallest in correct chronological order
        return nsmallest(n, (e for e in self._heap.events() if not e.CANCELED))

    def pop_event(self) -> Event:
        """Pop the first element from the event list."""
        return self._heap.pop()

    def compact(self) -> None:
        """Remove all canceled events from the heap and rebuild it.

        If there are many canceled events, compaction can speed up performance substantially.
        """
        self._heap.compact()

    def is_empty(self) -> bool:
        """Return whether the event list is empty."""
        return len(self) == 0

    def __contains__(self, event: Event) -> bool:  # noqa
        if event.CANCELED:
            return False
        return event in self._heap

    def __len__(self) -> int:  # noqa
        heap = self._heap
        return len(heap) - heap.canceled

    def __repr__(self) -> str:
        """Return a string representation of the event list."""
        events_str = ", ".join(
            [
                f"Event(time={e.time}, priority={e.priority}, id={e.unique_id})"
                for e in self._heap.events()
                if not e.CANCELED
            ]
        )
        return f"EventList([{events_str}])"

    def remove(self, event: Event) -> None:
        """Remove an event from the event list.

        Args:
            event (Event): The event to be removed

        """
        # We use lazy deletion: mark the event as canceled without
        # removing it from the heap to preserve heap invariants.
        # Canceled events are skipped during pop and may trigger
        # adaptive compaction if they dominate the heap.
        if not event.CANCELED:
            event.cancel()

    def clear(self) -> None:
        """Clear the event list, detaching the events so a later cancel() is not counted."""
        self._heap.clear()
