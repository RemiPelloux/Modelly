"""Agents as bytes, to send as ghosts or migrants to another partition.

A record is ``(class, unique_id, location, attributes)``: the agent's
``__dict__`` without its model, its cell and, for a ghost, its random streams
(a ghost never draws; a migrant takes its streams with it). An attribute that
refers to an agent, a model, a cell or a space (directly or as an item of a
list, tuple, set or dict) is refused, since that object would not exist in the
other partition.
"""

from __future__ import annotations

import pickle
import struct
from collections.abc import Callable, Iterable
from typing import Any

from modelly.core.agent import Agent
from modelly.core.model import Model
from modelly.core.rng import FastRandom, PyFastRandom
from modelly.core.streams import STREAM_ATTRIBUTES
from modelly.distributed.contract import PartitionError
from modelly.space.base import DiscreteSpace
from modelly.space.cells.cell import Cell
from modelly.space.continuous.space import ContinuousSpace

PROTOCOL = pickle.HIGHEST_PROTOCOL
# Attributes the receiving partition sets itself.
LOCAL_ATTRIBUTES = frozenset({"model", "_modelly_cell"})
GHOST_ATTRIBUTES = LOCAL_ATTRIBUTES | frozenset(STREAM_ATTRIBUTES)
RANDOM_ATTRIBUTE = STREAM_ATTRIBUTES[0]
WORD = "<{}I"  # Mersenne Twister state words: little-endian 32-bit, any platform


# Values that cannot refer to a simulation object, skipped without a check.
PLAIN = frozenset({int, float, bool, str, bytes, complex, type(None)})
CONTAINERS = (list, tuple, set, frozenset)
REFUSED = (Agent, Model, Cell, ContinuousSpace, DiscreteSpace)


def _check(agent: Agent, state: dict[str, Any]) -> None:
    """Refuse attributes (or their direct items) that are agents, models, cells or spaces."""
    for name, value in state.items():
        if type(value) in PLAIN:
            continue
        if isinstance(value, dict):
            items = value.values()
        else:
            items = value if isinstance(value, CONTAINERS) else (value,)
        for item in items:
            if isinstance(item, REFUSED):
                raise PartitionError(
                    f"{type(agent).__name__}.{name} refers to a {type(item).__name__}: "
                    "agents of a partitionable model hold plain data (keep the stream "
                    "key or the coordinate instead of the object)"
                )


def _unpack(version: int, words: bytes, gauss: float | None) -> FastRandom:
    """The ``FastRandom`` packed by ``_Packed``."""
    rng = FastRandom.__new__(FastRandom)
    count = len(words) // struct.calcsize(WORD.format(1))
    rng.setstate((version, struct.unpack(WORD.format(count), words), gauss))
    return rng


class _Packed:
    """Pickles a ``FastRandom`` as packed 32-bit words, not 625 Python ints.

    A migrant takes its stream with it; packed, the stream costs a few
    microseconds to send and load instead of tens.
    """

    __slots__ = ("rng",)

    def __init__(self, rng: FastRandom) -> None:
        """Wrap ``rng``."""
        self.rng = rng

    def __reduce__(self) -> tuple:
        """Rebuild through ``_unpack``."""
        version, words, gauss = self.rng.getstate()
        return _unpack, (version, struct.pack(WORD.format(len(words)), *words), gauss)


def state_of(agent: Agent, ghost: bool) -> dict[str, Any]:
    """The attributes of ``agent`` another partition needs."""
    skip = GHOST_ATTRIBUTES if ghost else LOCAL_ATTRIBUTES
    state = {k: v for k, v in agent.__dict__.items() if k not in skip}
    _check(agent, state)
    rng = state.get(RANDOM_ATTRIBUTE)
    if type(rng) in (FastRandom, PyFastRandom):
        state[RANDOM_ATTRIBUTE] = _Packed(rng)
    return state


def encode(agents: Iterable[Agent], location: Callable, ghost: bool) -> bytes:
    """The records of ``agents`` as bytes; ``location(agent)`` gives each place."""
    rows = [(type(a), a.unique_id, location(a), state_of(a, ghost)) for a in agents]
    try:
        return pickle.dumps(rows, protocol=PROTOCOL)
    except (pickle.PicklingError, TypeError, AttributeError) as error:
        raise PartitionError(
            f"cannot send agents to another partition: {error}. Agent classes of a "
            "split run are defined at module level and their attributes pickle"
        ) from error


def decode(data: bytes) -> list[tuple]:
    """The records written by ``encode``."""
    return pickle.loads(data)  # noqa: S301 - bytes from the run's own workers


def rebuild(record: tuple, model: Model) -> tuple[Agent, Any]:
    """An unregistered agent of ``model`` from ``record``, and its location."""
    kind, unique_id, location, state = record
    agent = kind.__new__(kind)
    agent.__dict__.update(state)
    agent.model = model
    agent.unique_id = unique_id
    return agent, location
