"""The loops behind ``AgentSet.select``, ``agg`` and ``get``: compiled when available.

The functions come from the C module ``fastset`` when it is built and not
disabled (``MODELLY_PURE_PYTHON=1``), else from the Python functions below,
which are the reference: both versions visit the same objects in the same
order, make the same calls and raise the same exceptions
(``tests/native/test_sets.py`` runs them side by side).
"""

from __future__ import annotations

import operator
import os
import weakref
from collections.abc import Callable, Iterable
from typing import Any


def py_keep_type(agents: list, agent_type: type) -> list:
    """The agents that are instances of ``agent_type``, in order."""
    return [a for a in agents if isinstance(a, agent_type)]


def py_keep_if(agents: list, filter_func: Callable[[Any], Any]) -> list:
    """The agents for which ``filter_func`` is truthy, in order."""
    return [a for a in agents if filter_func(a)]


def py_attr_values(agents: list, name: str) -> list:
    """``getattr(agent, name)`` for each agent (dotted names as attrgetter reads them)."""
    return list(map(operator.attrgetter(name), agents))


def py_live_agents(refs: dict) -> list:
    """The live referents of the weakref keys of ``refs``, from a snapshot, in order."""
    return [agent for r in list(refs) if (agent := r()) is not None]


def py_make_refs(agents: Iterable, callback: Callable) -> dict:
    """A dict keyed on ``weakref.ref(agent, callback)`` per agent, values None, in order."""
    ref = weakref.ref
    return dict.fromkeys([ref(agent, callback) for agent in agents])


def _load() -> Any:
    """The compiled module, or None when absent or disabled."""
    if os.environ.get("MODELLY_PURE_PYTHON"):
        return None
    try:
        from modelly._native import fastset  # noqa: PLC0415 - optional extension
    except ImportError:
        return None
    return fastset


_fastset = _load()
NATIVE: bool = _fastset is not None
keep_type = _fastset.keep_type if NATIVE else py_keep_type
keep_if = _fastset.keep_if if NATIVE else py_keep_if
attr_values = _fastset.attr_values if NATIVE else py_attr_values
live_agents = _fastset.live_agents if NATIVE else py_live_agents
make_refs = _fastset.make_refs if NATIVE else py_make_refs
