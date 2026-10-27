"""Reporters that reduce across partitions, and agent snapshots in key order.

A reducer wraps a function of a (partition's) model: ``Sum(count_infected)``
calls ``count_infected`` on every partition and adds the parts, ``Min`` and
``Max`` keep the smallest and largest. Integer sums, minima and maxima equal
the single-process value exactly; a float sum is added with ``math.fsum``, so
it does not depend on the order of the parts, but each part is rounded before
the parts are added: use integer reporters when byte identity matters.

``snapshot`` lists agents by stream key with their location and attributes;
the same call on a single-process model and on a split run gives equal frames.
"""

from __future__ import annotations

import math
import pickle
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from modelly.core.agent import Agent
    from modelly.core.model import Model

KEY = "key"
LOCATION = "location"
# Attributes that name the agent's model, cell and process-local id, not its state
# (a partition that builds only its own agents numbers them its own way).
PLACE_ATTRIBUTES = frozenset({"model", "_modelly_cell", "unique_id"})


def plain(value: Any) -> Any:
    """``value`` as a Python scalar when it is a numpy one (for JSON and equality)."""
    return value.item() if isinstance(value, np.generic) else value


@dataclass(frozen=True)
class Reducer:
    """A reporter: ``function(model)`` gives a partition's part of the value."""

    function: Callable[[Model], Any]

    def combine(self, parts: Sequence[Any]) -> Any:
        """The whole value from the parts of every partition."""
        raise NotImplementedError


class Sum(Reducer):
    """The sum of the parts (``math.fsum`` when any part is a float)."""

    def combine(self, parts: Sequence[Any]) -> Any:
        """Add the parts: exactly for integers, with ``math.fsum`` for floats."""
        values = [plain(part) for part in parts]
        if any(isinstance(value, float) for value in values):
            return math.fsum(values)
        return sum(values)


class Min(Reducer):
    """The smallest part."""

    def combine(self, parts: Sequence[Any]) -> Any:
        """The smallest part."""
        return plain(min(parts))


class Max(Reducer):
    """The largest part."""

    def combine(self, parts: Sequence[Any]) -> Any:
        """The largest part."""
        return plain(max(parts))


def location_of(agent: Agent) -> Any:
    """The agent's place: its cell coordinate, or its position as a tuple of floats."""
    cell = getattr(agent, "cell", None)
    if cell is not None:
        return cell.coordinate
    position = getattr(agent, "position", None)
    if position is None:
        return None
    return tuple(float(x) for x in position)


def records(agents: Iterable[Agent], attributes: Sequence[str]) -> list[tuple]:
    """``(stream key, location, *attributes)`` of each agent."""
    return [
        (a.stream_key(), location_of(a), *(plain(getattr(a, n)) for n in attributes))
        for a in agents
    ]


def states(agents: Iterable[Agent]) -> list[tuple]:
    """``(stream key, location, pickled attributes and streams)`` of each agent.

    Two runs agree on an agent when these tuples are equal: every attribute and
    the state of its random streams, byte for byte.
    """
    return [
        (
            a.stream_key(),
            location_of(a),
            pickle.dumps(
                {k: v for k, v in vars(a).items() if k not in PLACE_ATTRIBUTES},
                protocol=pickle.HIGHEST_PROTOCOL,
            ),
        )
        for a in agents
    ]


def frame_of(rows: Iterable[tuple], attributes: Sequence[str]) -> pd.DataFrame:
    """The records as a frame indexed by stream key, in key order."""
    frame = pd.DataFrame(list(rows), columns=[KEY, LOCATION, *attributes])
    return frame.set_index(KEY).sort_index()


def snapshot(model: Model, attributes: Sequence[str] = ()) -> pd.DataFrame:
    """The agents of a single-process model by stream key, with location and attributes.

    Example:
        >>> snapshot(model, ["state"])  # doctest: +SKIP
    """
    return frame_of(records(model.agents, attributes), attributes)
