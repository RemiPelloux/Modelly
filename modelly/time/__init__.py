"""Underlying modules for event scheduling and time advancement.

This module provides the foundational data structures and classes needed for event-based
simulation in Modelly. The EventList class is a priority queue implementation that maintains
simulation events in chronological order while respecting event priorities. Key features:

- Priority-based event ordering
- Weak references to prevent memory leaks from canceled events
- Efficient event insertion and removal using a heap queue
- Support for event cancellation without breaking the heap structure
"""

from modelly.time.events.event import Event, Priority
from modelly.time.events.event_list import EventList
from modelly.time.events.generator import EventGenerator, Schedule

__all__ = ["Event", "EventGenerator", "EventList", "Priority", "Schedule"]
