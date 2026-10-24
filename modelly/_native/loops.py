"""The framework's per-agent and per-cell loops: compiled when available.

``call_each`` and ``neighborhood`` come from the C module ``fastloop`` when it
is built and not disabled (``MODELLY_PURE_PYTHON=1``), else from the Python
functions below. Both versions visit the same objects in the same order and
make the same calls, so a model gives the same results either way
(``tests/native/test_loops.py`` runs them side by side).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any


def py_call_each(
    order: list, members: dict, method: str | Callable, args: tuple, kwargs: dict | None
) -> None:
    """Call ``method`` on each agent of ``order`` that is still a key of ``members``."""
    kwargs = kwargs or {}
    if isinstance(method, str):
        for agent in order:
            if agent in members:
                getattr(agent, method)(*args, **kwargs)
    else:
        for agent in order:
            if agent in members:
                method(agent, *args, **kwargs)


def py_neighborhood(cell: Any, radius: int) -> dict:
    """Cells within ``radius`` hops of ``cell`` (itself excluded), in BFS order.

    Each cell maps to its live ``_agents`` list. The result dict doubles as the
    visited set: ``cell`` is seeded into it and dropped at the end.
    """
    reached = {cell: cell._agents}
    frontier = []
    for neighbor in cell.connections.values():
        if neighbor not in reached:
            reached[neighbor] = neighbor._agents
            frontier.append(neighbor)
    for _ in range(radius - 1):
        if not frontier:
            break
        next_frontier = []
        for current in frontier:
            for neighbor in current.connections.values():
                if neighbor not in reached:
                    reached[neighbor] = neighbor._agents
                    next_frontier.append(neighbor)
        frontier = next_frontier
    del reached[cell]
    return reached


def _load() -> Any:
    """The compiled module, or None when absent or disabled."""
    if os.environ.get("MODELLY_PURE_PYTHON"):
        return None
    try:
        from modelly._native import fastloop  # noqa: PLC0415 - optional extension
    except ImportError:
        return None
    return fastloop


_fastloop = _load()
NATIVE: bool = _fastloop is not None
call_each = _fastloop.call_each if NATIVE else py_call_each
neighborhood = _fastloop.neighborhood if NATIVE else py_neighborhood
