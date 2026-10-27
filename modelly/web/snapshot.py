"""What the browser runner draws: the agents' places in space and the model reporters.

Plain functions of a model that return JSON-ready values, so the page's space view and
plot read the same data in Pyodide and the tests read it in CPython.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np

from modelly.space.continuous.space import ContinuousSpace
from modelly.space.grid.base import Grid
from modelly.timetravel.snapshot import agent_state

if TYPE_CHECKING:
    from modelly.core.agent import Agent
    from modelly.core.model import Model

CLASS = "class"
# A space view of more agents than this draws the first ones only.
MAX_POINTS = 20_000
PLACE_NAMES = frozenset({"cell", "position"})
PLANE = 2


def _space(model: Model) -> Any:
    """The model's grid or continuous space, the first found among its attributes."""
    for value in vars(model).values():
        if isinstance(value, Grid | ContinuousSpace):
            return value
    return None


def _bounds(space: Any) -> list[float] | None:
    """``[x_min, y_min, x_max, y_max]`` of a grid or continuous space, else None."""
    if isinstance(space, Grid):
        return [0.0, 0.0, float(space.width), float(space.height)]
    if isinstance(space, ContinuousSpace):
        return [float(v) for v in (space.x_min, space.y_min, space.x_max, space.y_max)]
    return None


def _place(agent: Agent) -> tuple[float, float] | None:
    """The agent's ``(x, y)``: its cell's position or its own, None when it has none."""
    cell = getattr(agent, "cell", None)
    where = cell.position if cell is not None else getattr(agent, "position", None)
    if where is None:
        return None
    xy = np.asarray(where, dtype=float).ravel()
    return (float(xy[0]), float(xy[1])) if xy.size >= PLANE else None


def _number(value: Any) -> float | None:
    """``value`` as a float for the colour scale, None when it is not a finite number."""
    if isinstance(value, bool | int | float | np.number):
        number = float(value)
        return number if math.isfinite(number) else None
    return None


def colour_attributes(model: Model) -> list[str]:
    """The numeric attributes of the agents the space view can colour by, sorted."""
    seen: dict[str, Agent] = {}
    for agent in model.agents:
        seen.setdefault(type(agent).__name__, agent)
    names = set()
    for agent in seen.values():
        names.update(
            name
            for name, value in agent_state(agent).items()
            if name not in PLACE_NAMES and _number(value) is not None
        )
    return sorted(names)


def _points(model: Model, colour_by: str) -> tuple[list[list], list[str]]:
    """``[x, y, value]`` per placed agent (at most MAX_POINTS) and the class names seen."""
    classes: list[str] = []
    points = []
    for agent in model.agents:
        place = _place(agent)
        if place is None:
            continue
        if colour_by == CLASS:
            name = type(agent).__name__
            if name not in classes:
                classes.append(name)
            value = classes.index(name)
        else:
            value = _number(getattr(agent, colour_by, None))
        points.append([*place, value])
        if len(points) >= MAX_POINTS:
            break
    return points, classes


def space_view(model: Model, colour_by: str = CLASS) -> dict[str, Any] | None:
    """The agents' places and colour values, or None when no agent has a place.

    Each point is ``[x, y, value]``: the index of the agent's class name in ``classes``
    when ``colour_by`` is ``class``, else the agent's ``colour_by`` attribute (None when
    it has none). ``cells`` tells the page to draw grid squares instead of dots.
    """
    points, classes = _points(model, colour_by)
    if not points:
        return None
    space = _space(model)
    return {
        "cells": isinstance(space, Grid),
        "bounds": _bounds(space),
        "classes": classes,
        "points": points,
    }


def series_rows(model: Model, start: int = 0) -> dict[str, list] | None:
    """The numeric model reporters collected from row ``start`` on, by name, or None."""
    collector = getattr(model, "datacollector", None)
    if collector is None or not getattr(collector, "model_reporters", None):
        return None
    frame = collector.get_model_vars_dataframe().select_dtypes("number")
    if frame.empty:
        return None
    rows = frame.iloc[start:].astype(float)
    return {
        str(name): [None if math.isnan(v) else v for v in rows[name].tolist()]
        for name in rows.columns
    }


__all__ = ["colour_attributes", "series_rows", "space_view"]
