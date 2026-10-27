"""The heap behind ``EventList``: compiled when available.

``EventHeap`` is the C type of the module ``fastevents`` when it is built and
not disabled (``MODELLY_PURE_PYTHON=1``), else ``PyEventHeap`` below, which is
the reference: both run the standard library's ``heapq`` steps on
``Event.__lt__`` (time, then priority, then insertion order), so for the same
calls they hold the same array and pop the same events in the same order
(``tests/native/test_events.py`` runs them side by side). Both pickle through
``EventList``, as the list of events in heap order, so a checkpoint written
with one loads with the other.

The compiled heap reads an event's time, priority and unique id once, when it
is pushed, and compares them as C numbers; an event's time and priority must
not change while it is on a list, as they never could without breaking the heap.
"""

from __future__ import annotations

import os
from heapq import heapify, heappop, heappush
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from modelly.time.events.event import Event


class PyEventHeap:
    """A binary heap of events, with a count of the canceled events it still holds."""

    __slots__ = ("_items", "canceled")

    def __init__(self, events: Any = ()) -> None:
        """Hold ``events`` in their given order, which must already be a heap."""
        self._items: list[Event] = list(events)
        self.canceled: int = 0

    def __len__(self) -> int:
        """Events held, canceled ones included."""
        return len(self._items)

    def __contains__(self, event: Any) -> bool:
        """Whether ``event`` is held (canceled or not)."""
        return event in self._items

    def push(self, event: Event) -> None:
        """Add ``event`` (``heapq.heappush``)."""
        heappush(self._items, event)

    def pop(self) -> Event:
        """Remove and return the first live event, dropping canceled ones on the way.

        Raises:
            IndexError: If no live event is left.
        """
        items = self._items
        while items:
            event = heappop(items)
            if not event.CANCELED:
                # No longer on the heap, so a later cancel() must not be counted here.
                event._owner = None
                return event
            self.canceled -= 1
        raise IndexError("Event list is empty")

    def pop_due(self, until: Any) -> Event | None:
        """Remove and return the first live event if its time is ``<= until``, else None."""
        items = self._items
        while items:
            first = items[0]
            if first.CANCELED:
                heappop(items)
                self.canceled -= 1
            elif first.time <= until:
                heappop(items)
                first._owner = None
                return first
            else:
                return None
        return None

    def compact(self) -> None:
        """Drop the canceled events and rebuild the heap."""
        self._items = [e for e in self._items if not e.CANCELED]
        heapify(self._items)
        self.canceled = 0

    def clear(self) -> None:
        """Detach every event, so a later cancel() is not counted, and drop them all."""
        for event in self._items:
            event._owner = None
        self._items.clear()
        self.canceled = 0

    def events(self) -> list[Event]:
        """The events, canceled ones included, in heap order (a copy)."""
        return list(self._items)


def _load() -> Any:
    """The compiled module bound to ``Event``, or None when absent or disabled."""
    if os.environ.get("MODELLY_PURE_PYTHON"):
        return None
    try:
        from modelly._native import fastevents  # noqa: PLC0415 - optional extension
    except ImportError:
        return None
    from modelly.time.events.event import Event  # noqa: PLC0415 - imports this module

    fastevents.bind(Event, np.float64)
    return fastevents


_fastevents = _load()
NATIVE: bool = _fastevents is not None
EventHeap = _fastevents.EventHeap if NATIVE else PyEventHeap
