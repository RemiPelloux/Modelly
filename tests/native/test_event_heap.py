"""The compiled event heap gives exactly what its Python twin gives."""

import gc
import math
import random
import weakref
from fractions import Fraction

import numpy as np
import pytest

from modelly import Model
from modelly._native import events
from modelly.time.events.event import Event, Priority

pytestmark = pytest.mark.skipif(not events.NATIVE, reason="fastevents is not built")
EventHeap = events._fastevents.EventHeap if events.NATIVE else None
PRIORITIES = (Priority.HIGH, Priority.DEFAULT, Priority.LOW)
SEEDS = range(12)


def handler():
    """A module-level callback, so events pickle."""


class LateEvent(Event):
    """A subclass: compared through ``__lt__``, as heapq compares it."""


def random_time(draw: random.Random):
    """Times of every kind the heap meets: exact, numpy, huge ints, fractions, ties."""
    kind = draw.randrange(7)
    if kind == 0:
        return draw.randrange(20)  # many ties, broken by priority then id
    if kind == 1:
        return np.float64(draw.randrange(40) / 2)
    if kind == 2:
        return 2**60 + draw.randrange(3)  # not exact as a double: compared by Python
    if kind == 3:
        return Fraction(draw.randrange(60), 3)
    return draw.random() * 20


def make_event(draw: random.Random) -> Event:
    """A random event; one in eight is a subclass instance."""
    kind = LateEvent if draw.random() < 1 / 8 else Event
    return kind(random_time(draw), handler, priority=draw.choice(PRIORITIES))


def run_script(heap, seed: int) -> list:
    """A random mix of pushes, pops, due-pops, cancels, compactions; what came out.

    Events are named by their creation index, so two runs compare equal.
    """
    draw, out, held, name = random.Random(seed), [], [], {}
    for _ in range(400):
        action = draw.random()
        if action < 0.5:
            event = make_event(draw)
            name[event.unique_id] = len(name)
            held.append(event)
            heap.push(event)
        elif action < 0.65 and len(heap) > heap.canceled:
            out.append(name[heap.pop().unique_id])
        elif action < 0.8:
            due = heap.pop_due(draw.randrange(25))
            out.append(None if due is None else name[due.unique_id])
        elif action < 0.95 and held:
            victim = held.pop(draw.randrange(len(held)))
            if not victim.CANCELED and victim in heap:
                victim._canceled = True
                heap.canceled += 1
        else:
            heap.compact()
        out.append([name[e.unique_id] for e in heap.events()])
    return out


@pytest.mark.parametrize("seed", SEEDS)
def test_random_schedules_give_the_same_order_and_array(seed):
    """Every pop and the whole heap array match the twin's after every operation."""
    assert run_script(EventHeap(), seed) == run_script(events.PyEventHeap(), seed)


@pytest.mark.parametrize("seed", SEEDS)
def test_draining_gives_time_priority_insertion_order(seed):
    """Exact keys only: the drained order is the sorted order of (time, priority, id)."""
    draw = random.Random(seed)
    heap = EventHeap()
    pushed = [
        Event(draw.randrange(10), handler, draw.choice(PRIORITIES)) for _ in range(300)
    ]
    for event in pushed:
        heap.push(event)
    drained = [heap.pop() for _ in range(len(pushed))]
    assert drained == sorted(pushed, key=lambda e: (e.time, e.priority, e.unique_id))


def test_nan_times_compare_as_the_twin_compares():
    """NaN breaks the order for both alike: same comparisons, same array."""
    twin, compiled = events.PyEventHeap(), EventHeap()
    batch = [Event(t, handler) for t in (3.0, math.nan, 1.0, math.nan, 2.0, 0.5)]
    for event in batch:
        twin.push(event)
        compiled.push(event)
    assert compiled.events() == twin.events()
    assert [compiled.pop() for _ in batch] == [twin.pop() for _ in batch]


def test_pop_due_skips_canceled_and_leaves_later_events():
    """Canceled roots are dropped and counted; a later event stays on the heap."""
    heap = EventHeap()
    first, later = Event(1.0, handler), Event(5.0, handler)
    for event in (first, later):
        heap.push(event)
    first._canceled = True
    heap.canceled = 1
    assert heap.pop_due(4) is None
    assert heap.canceled == 0
    assert heap.events() == [later]
    assert heap.pop_due(Fraction(5)) is later
    with pytest.raises(IndexError, match="Event list is empty"):
        heap.pop()


def test_a_raising_comparison_propagates():
    """An error in ``__lt__`` comes out of push, as it does from heapq."""

    class Broken(Event):
        def __lt__(self, other):
            raise ArithmeticError("no order")

    heap = EventHeap([Event(1.0, handler)])
    with pytest.raises(ArithmeticError):
        heap.push(Broken(0.0, handler))
    assert len(heap) == 2  # the event is held, as heapq leaves it in the list


def test_reentrant_comparison_is_refused():
    """A comparison that changes the heap it is sifting gets RuntimeError."""
    heap = EventHeap()

    class Meddling(Event):
        def __lt__(self, other):
            heap.push(Event(0.0, handler))
            return True

    heap.push(Event(1.0, handler))
    with pytest.raises(RuntimeError, match="changed while"):
        heap.push(Meddling(0.0, handler))


def test_heap_releases_its_events_and_cycles():
    """No leaks: clear, compact and collection release every event."""
    model = Model(rng=1)
    probe = Event(1.0, handler, function_args=[model])
    model._event_list.add_event(probe)
    alive = weakref.ref(probe)
    del probe, model
    gc.collect()
    assert alive() is None


def test_contains_and_len():
    """``in`` is membership by identity; ``len`` counts canceled events too."""
    heap = EventHeap()
    event = Event(2.0, handler)
    heap.push(event)
    assert event in heap
    assert Event(2.0, handler) not in heap
    assert len(heap) == 1
