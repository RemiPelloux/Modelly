"""Collect per-agent plotting data into the NumPy arrays Matplotlib's scatter takes.

Shared by ``collect_agent_data`` here and ``MatplotlibBackend.collect_agent_data``.
"""

import warnings
from collections.abc import Callable
from operator import attrgetter

import numpy as np

import modelly
from modelly.space import (
    DiscreteSpace,
    OrthogonalMooreGrid,
    OrthogonalVonNeumannGrid,
    VoronoiGrid,
)
from modelly.space.continuous import ContinuousSpace
from modelly.viz.render.portrayal import (
    dict_to_style,
    style_defaults,
    warn_dict_portrayal,
)

OrthogonalGrid = OrthogonalMooreGrid | OrthogonalVonNeumannGrid
HexGrid = modelly.space.HexGrid
Network = modelly.space.Network

# Argument names, in the order the collected dict has always had.
ARGUMENT_KEYS = (
    "loc",
    "s",
    "c",
    "marker",
    "zorder",
    "alpha",
    "edgecolors",
    "linewidths",
)
# One C-level call snapshots every style field an agent row needs.
_IGNORED_MSG = "The following keys from the returned dict were ignored: "
snapshot_style = attrgetter(
    "x", "y", "color", "marker", "zorder", "alpha", "edgecolors", "linewidths"
)


def _to_numpy_argument_array(key: str, value: list) -> np.ndarray:
    """Convert a per-agent argument list into a NumPy array for Matplotlib.

    This is shared by both matplotlib-based ``collect_agent_data`` implementations
    (this module and ``MatplotlibBackend``) so the array-construction rules for
    "tricky" arguments only need to be maintained in one place.

    Args:
        key: the argument name (e.g. "marker", "edgecolors", "s", "c", ...).
        value: the list of per-agent values collected for that argument, with
            exactly one entry per agent so positions stay aligned.

    Returns:
        A NumPy array suitable for passing to Matplotlib's scatter call.
    """
    if key == "marker":
        arr = np.empty(len(value), dtype=object)
        arr[:] = value
        return arr

    if key == "edgecolors":
        if not any(edgecolor is not None for edgecolor in value):
            return np.asarray([])

        normalized = [
            edgecolor if edgecolor is not None else "none" for edgecolor in value
        ]
        return _coerce_color_array(normalized)

    if key == "c":
        return _coerce_color_array(value)
    return np.asarray(value)


def _coerce_color_array(value: list) -> np.ndarray:
    """Try a normal array first; fall back to a manual 1D object array.

    Color-like argument lists can freely mix plain color-name strings, RGBA/RGB tuples,
    and (for edge colors) the "none" sentinel. When every entry has a consistent shape, and (for edgecolors) the "none" sentinel.
    When every entry has a consistent shape, we can use np.asarray() does the right thing on its own. When it doesn't
    e.g. a string next to a 4 tuple -- it raises ValueError, and we build the array by hand instead so each entry stays intact as one element.
    """
    try:
        return np.asarray(value)
    except ValueError:
        arr = np.empty(len(value), dtype=object)
        arr[:] = value
        return arr


def rows_to_arguments(rows: list) -> dict:
    """Turn ``(size, *snapshot_style(aps))`` rows into the scatter argument arrays."""
    columns = list(zip(*rows)) if rows else [()] * (len(ARGUMENT_KEYS) + 1)
    size, x, y, *style = columns
    values = [list(zip(x, y)), list(size), *(list(column) for column in style)]
    return {
        key: _to_numpy_argument_array(key, value)
        for key, value in zip(ARGUMENT_KEYS, values)
    }


def portrayal_style_defaults() -> dict:
    """Return the AgentPortrayalStyle field defaults by field name."""
    return style_defaults()


def style_from_dict(portray_input: dict, position, style_fields: dict, ignored_msg):
    """Build an AgentPortrayalStyle from a legacy portrayal dict.

    Warns with ``ignored_msg`` followed by the names of the keys it did not use.
    """
    aps, ignored_keys = dict_to_style(portray_input, position, style_fields)
    if ignored_keys:
        warnings.warn(
            f"{ignored_msg}{', '.join(ignored_keys)}",
            UserWarning,
            stacklevel=3,  # the caller of collect_agent_data()
        )
    return aps


def _agent_position(agent, space):
    """Return the agent position depending on the grid type."""
    if isinstance(space, DiscreteSpace):
        agent_x, agent_y = agent.cell.position
    else:
        agent_x, agent_y = agent.position
    return agent_x, agent_y


def collect_agent_data(
    space: OrthogonalGrid | HexGrid | Network | ContinuousSpace | VoronoiGrid,
    agent_portrayal: Callable,
    default_size: float | None = None,
) -> dict:
    """Collect the plotting data for all agents in the space.

    Args:
        space: The space containing the Agents.
        agent_portrayal: A callable that is called with the agent and returns a AgentPortrayalStyle
        default_size: default size

    agent_portrayal should return a AgentPortrayalStyle, limited to size (size of marker), color (color of marker), zorder (z-order),
    marker (marker style), alpha, linewidths, and edgecolors.
    """
    style_fields = portrayal_style_defaults()
    class_default_size = style_fields.get("size")
    fallback_size = default_size if default_size is not None else class_default_size
    dict_portrayal_warned = False  # Warn only once per call instead of once per agent
    rows = []
    for agent in space.agents:
        portray_input = agent_portrayal(agent)
        if isinstance(portray_input, dict):
            if not dict_portrayal_warned:
                warn_dict_portrayal()
                dict_portrayal_warned = True
            position = _agent_position(agent, space)
            aps = style_from_dict(portray_input, position, style_fields, _IGNORED_MSG)
        else:
            aps = portray_input
            # default to agent's color if not provided
            if aps.edgecolors is None and not isinstance(
                aps.color, int | float | np.number
            ):
                aps.edgecolors = aps.color
            if aps.x is None and aps.y is None:  # get position if not specified
                aps.x, aps.y = _agent_position(agent, space)
        size = aps.size if aps.size is not None else fallback_size
        rows.append((size, *snapshot_style(aps)))
    return rows_to_arguments(rows)
