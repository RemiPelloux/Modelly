"""A reporter factory: the share of agents whose attribute has a value."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any


def _share(model: Any, attribute: str, value: Any) -> float:
    """The share of ``model.agents`` with ``attribute == value``; 0 without agents."""
    agents = model.agents
    if not agents:
        return 0.0
    return sum(getattr(a, attribute) == value for a in agents) / len(agents)


def share_of(attribute: str, value: Any) -> Callable[[Any], float]:
    """A model reporter: the share of agents with ``attribute == value``.

    A ``functools.partial`` of a module-level function, so models that use it can
    still be saved and run in other processes.
    """
    return partial(_share, attribute=attribute, value=value)
