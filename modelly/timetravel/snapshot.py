"""Stable snapshots of model and agent state, and their first difference.

An agent's snapshot is its ``unique_id``, class name and the values that make
up its state: its ``Column`` values, the scalars in its ``__dict__`` (names
starting with ``_`` excluded) and where it is (``cell`` coordinate or
``position``). Short numpy vectors and tuples of scalars count as scalars;
lists, sets, other agents and objects do not. The model's snapshot adds its own
scalars and a digest of each random generator's state.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from modelly.timetravel.report import Difference

if TYPE_CHECKING:
    from modelly.core.agent import Agent
    from modelly.core.model import Model

SCALARS = (bool, int, float, complex, str, bytes, type(None))
# Longest numpy vector kept in a snapshot, e.g. a heading or a position.
MAX_VECTOR = 16
DIGEST_CHARS = 16
SKIPPED_NAMES = frozenset({"model", "unique_id"})
_SKIP = object()


def _value(value: Any) -> Any:
    """``value`` as a comparable plain value, or ``_SKIP`` when it is not state."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, SCALARS):
        return value
    if isinstance(value, np.ndarray) and value.ndim == 1 and value.size <= MAX_VECTOR:
        return tuple(value.tolist())
    if isinstance(value, tuple) and all(isinstance(v, SCALARS) for v in value):
        return value
    return _SKIP


def _scalars(namespace: dict[str, Any]) -> Iterator[tuple[str, Any]]:
    """The public scalar entries of an instance ``__dict__``."""
    for name, raw in namespace.items():
        if name.startswith("_") or name in SKIPPED_NAMES:
            continue
        value = _value(raw)
        if value is not _SKIP:
            yield name, value


def _place(agent: Agent) -> tuple[str, Any] | None:
    """``("cell", coordinate)`` or ``("position", xy)``, or None."""
    cell = getattr(agent, "cell", None)
    if cell is not None:
        return "cell", _value(getattr(cell, "coordinate", None))
    position = getattr(agent, "position", None)
    if position is not None:
        return "position", _value(np.asarray(position))
    return None


def agent_state(agent: Agent) -> dict[str, Any]:
    """The state of ``agent``: columns, ``__dict__`` scalars and place."""
    state = dict(_scalars(vars(agent)))
    for name in getattr(type(agent), "_column_specs", {}):
        state[name] = _value(getattr(agent, name))
    place = _place(agent)
    if place is not None:
        state[place[0]] = place[1]
    return state


def _digest(state: Any) -> str:
    """A short, stable digest of a generator state."""
    return hashlib.sha256(repr(state).encode()).hexdigest()[:DIGEST_CHARS]


@dataclass(frozen=True)
class ModelState:
    """A model's snapshot: its scalars, its agents and its generators."""

    model: dict[str, Any]
    agents: dict[int, tuple[str, dict[str, Any]]]
    generators: dict[str, str]


def model_state(model: Model) -> ModelState:
    """The snapshot of ``model`` and every agent it holds."""
    agents = {
        agent.unique_id: (type(agent).__qualname__, agent_state(agent))
        for agent in model.agents
    }
    generators = {
        "random": _digest(model.random.getstate()),
        "rng": _digest(model.rng.bit_generator.state),
    }
    return ModelState(dict(_scalars(vars(model))), agents, generators)


def same(a: Any, b: Any) -> bool:
    """Whether two snapshot or data values are equal, NaN equal to NaN."""
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a):
        return math.isnan(b)
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        return bool(np.array_equal(a, b))
    return bool(a == b)


def first_value_difference(
    a: dict[str, Any], b: dict[str, Any], step: float, **who: Any
) -> Difference | None:
    """The first name, in ``a``'s order then ``b``'s, whose values differ."""
    for name in {**a, **b}:
        left, right = a.get(name, "<missing>"), b.get(name, "<missing>")
        if not same(left, right):
            return Difference(step, name, left, right, **who)
    return None


def _first_agent_difference(
    a: ModelState, b: ModelState, step: float
) -> Difference | None:
    """The first agent, by ``unique_id``, whose class or state differs."""
    for uid in sorted(a.agents.keys() | b.agents.keys()):
        if uid not in a.agents or uid not in b.agents:
            kind = (a.agents.get(uid) or b.agents[uid])[0]
            return Difference(
                step, "exists", uid in a.agents, uid in b.agents, uid, kind
            )
        (kind_a, state_a), (kind_b, state_b) = a.agents[uid], b.agents[uid]
        if kind_a != kind_b:
            return Difference(step, "class", kind_a, kind_b, uid, kind_a)
        found = first_value_difference(
            state_a, state_b, step, agent=uid, agent_class=kind_a
        )
        if found is not None:
            return found
    return None


def first_state_difference(
    a: ModelState, b: ModelState, step: float
) -> Difference | None:
    """The first difference: model scalars, then agents, then generators."""
    return (
        first_value_difference(a.model, b.model, step)
        or _first_agent_difference(a, b, step)
        or first_value_difference(a.generators, b.generators, step)
    )
