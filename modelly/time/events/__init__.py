"""Core event management for Modelly's discrete event simulation system.

This package provides the foundational data structures and classes needed for event-based
simulation in Modelly. The EventList class is a priority queue implementation that maintains
simulation events in chronological order while respecting event priorities. Key features:

- Priority-based event ordering
- Weak references to prevent memory leaks from canceled events
- Efficient event insertion and removal using a heap queue
- Support for event cancellation without breaking the heap structure
- Adaptive compaction, so repeated cancellation does not grow the heap without bound

The package contains these main components:
- Priority: An enumeration defining event priority levels (HIGH, DEFAULT, LOW)
- Event: A class representing individual events with timing and execution details
- EventList: A heap-based priority queue managing the chronological ordering of events
- Schedule and EventGenerator: recurring events

The implementation supports both pure discrete event simulation and hybrid approaches
combining agent-based modeling with event scheduling.
"""

from modelly.time.events.event import Event, Priority
from modelly.time.events.event_list import EventList
from modelly.time.events.generator import EventGenerator, Schedule

__all__ = [
    "Event",
    "EventGenerator",
    "EventList",
    "Priority",
    "Schedule",
]
