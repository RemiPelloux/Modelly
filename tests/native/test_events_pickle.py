"""Event lists and checkpoints move between the compiled heap and its Python twin."""

import gc
import inspect
import pickle
import random
import subprocess
import sys
from fractions import Fraction

import numpy as np
import pytest

from modelly._native import events
from modelly.time.events.event import Event, Priority
from modelly.time.events.event_list import EventList

pytestmark = pytest.mark.skipif(not events.NATIVE, reason="fastevents is not built")
PRIORITIES = (Priority.HIGH, Priority.DEFAULT, Priority.LOW)
TIMES = (3, 3.5, np.float64(3.5), 2**60, Fraction(7, 2), 0.25)


def drain(event_list):
    """Pop every live event: (unique_id, time) in order."""
    order = []
    while not event_list.is_empty():
        event = event_list.pop_event()
        order.append((event.unique_id, float(event.time)))
    return order


# In the other interpreter: load the list, pickle it again with that implementation's
# heap, then drain it; print which heap ran, the drained order and the new pickle.
PICKLED_RUN = """
import pickle, sys
from modelly._native import events
event_list = pickle.loads(sys.stdin.buffer.read())
again = pickle.dumps(event_list)
print(events.NATIVE, repr(drain(event_list)).replace(" ", ""), again.hex())
"""

# In the other interpreter: resume a wolf-sheep checkpoint and print what it collects.
CHECKPOINT_RUN = """
import sys
from modelly.examples.advanced.wolf_sheep.model import WolfSheep
model = WolfSheep.load(sys.stdin.readline().strip())
model.run_for(15)
print(repr((model.datacollector.model_vars, model.random.random())).replace(" ", ""))
"""


def in_other_interpreter(script: str, payload: bytes, pure: bool) -> list[str]:
    """Run ``script`` with or without the compiled modules; its stdout, split."""
    env = {"MODELLY_PURE_PYTHON": "1" if pure else "", "PYTHONPATH": ":".join(sys.path)}
    done = subprocess.run(
        [sys.executable, "-c", inspect.getsource(drain) + script],
        input=payload,
        capture_output=True,
        check=True,
        env=env,
    )
    return done.stdout.decode().split()


def schedule_list() -> EventList:
    """An event list with ties, numpy times, huge ints, fractions and a canceled event.

    The callback is a builtin, so the other interpreter can unpickle it.
    """
    draw, event_list = random.Random(5), EventList()
    batch = [
        Event(draw.choice(TIMES), gc.collect, priority=draw.choice(PRIORITIES))
        for _ in range(60)
    ]
    for event in batch:
        event_list.add_event(event)
    batch[7].cancel()
    return event_list


def test_pickles_load_in_both_directions():
    """Compiled to pure and pure to compiled: same heap array, same drained order."""
    original = schedule_list()
    payload = pickle.dumps(original)
    native, order, written = in_other_interpreter(PICKLED_RUN, payload, pure=True)
    assert native == "False"
    from_pure = pickle.loads(bytes.fromhex(written))  # noqa: S301 - written just above
    from_compiled = pickle.loads(payload)  # noqa: S301 - written just above
    ids = [e.unique_id for e in original._events]
    assert [e.unique_id for e in from_pure._events] == ids
    assert from_pure._n_canceled == from_compiled._n_canceled == 1
    expected = drain(from_compiled)
    assert drain(from_pure) == expected
    assert order == repr(expected).replace(" ", "")


@pytest.mark.parametrize("pure", [True, False])
def test_checkpoint_resumes_identically_in_either_implementation(tmp_path, pure):
    """Wolf-sheep (a regrowth event per eaten patch) saved compiled, resumed by either."""
    from modelly.examples.advanced.wolf_sheep.model import (  # noqa: PLC0415
        WolfSheep,
        WolfSheepScenario,
    )

    model = WolfSheep(WolfSheepScenario(rng=3))
    model.run_for(5)
    path = tmp_path / "wolf_sheep.ckpt"
    model.save(path)
    lines = in_other_interpreter(CHECKPOINT_RUN, f"{path}\n".encode(), pure=pure)
    model.run_for(15)
    expected = (model.datacollector.model_vars, model.random.random())
    assert lines == [repr(expected).replace(" ", "")]
