"""Helpers that turn agent portrayals into the column arrays the Altair backend draws."""

import warnings
from dataclasses import fields

import numpy as np

# Marker mapping from Matplotlib to Altair
MARKER_TO_SHAPE = {
    "o": "circle",
    "s": "square",
    "D": "diamond",
    "^": "triangle-up",
    "v": "triangle-down",
    "<": "triangle-left",
    ">": "triangle-right",
    "+": "cross",
    "x": "cross",  # Both '+' and 'x' map to cross in Altair
    ".": "circle",  # Small point becomes circle
    "1": "triangle-down",
    "2": "triangle-up",
    "3": "triangle-left",
    "4": "triangle-right",
}

AGENT_DATA_KEYS = (
    "loc",
    "size",
    "color",
    "shape",
    "order",  # z-order
    "opacity",
    "stroke",  # Stroke color
    "strokeWidth",
    "filled",
    "tooltip",
)
_FLOAT_KEYS = ("x", "y", "size", "order", "opacity", "strokeWidth")
_DICT_STYLE_KEYS = (
    "size",
    "color",
    "marker",
    "zorder",
    "alpha",
    "edgecolors",
    "linewidths",
)

# The helpers below warn on behalf of ``AltairBackend.collect_agent_data``; this
# stacklevel attributes the warning to that method's caller.
_CALLER_STACKLEVEL = 3


def style_defaults() -> dict:
    """Return the default value of every AgentPortrayalStyle field."""
    # Import here to avoid circular import issues
    from modelly.viz.components import AgentPortrayalStyle  # noqa: PLC0415

    return {f.name: f.default for f in fields(AgentPortrayalStyle)}


def warn_dict_portrayal() -> None:
    """Warn that returning a dict from agent_portrayal is deprecated."""
    warnings.warn(
        (
            "Returning a dict from agent_portrayal is deprecated and will be removed in a future release. "
            "Please return an AgentPortrayalStyle instance instead. "
            "For more information, refer to the migration guide: "
        ),
        FutureWarning,
        stacklevel=_CALLER_STACKLEVEL,
    )


def style_from_dict(portray_input: dict, position, style_fields: dict):
    """Build an AgentPortrayalStyle from a (deprecated) dict portrayal."""
    from modelly.viz.components import AgentPortrayalStyle  # noqa: PLC0415

    dict_data = portray_input.copy()
    agent_x, agent_y = position
    styles = {
        key: dict_data.pop(key, style_fields.get(key)) for key in _DICT_STYLE_KEYS
    }
    aps = AgentPortrayalStyle(x=agent_x, y=agent_y, **styles)
    if dict_data:
        ignored_keys = list(dict_data.keys())
        warnings.warn(
            f"The following keys were ignored from dict portrayal: {', '.join(ignored_keys)}",
            UserWarning,
            stacklevel=_CALLER_STACKLEVEL,
        )
    return aps


def unsupported_marker(raw_marker) -> str:
    """Warn that ``raw_marker`` has no Altair shape and fall back to a circle."""
    warnings.warn(
        f"Marker '{raw_marker}' is not supported in Altair. Using 'circle' as default.",
        UserWarning,
        stacklevel=_CALLER_STACKLEVEL,
    )
    return "circle"


def to_arrays(arguments: dict) -> dict:
    """Convert the collected per-agent lists into numpy arrays."""
    final_data = {}
    for k, v in arguments.items():
        if k == "shape":
            # Ensure shape is an object array
            arr = np.empty(len(v), dtype=object)
            arr[:] = v
            final_data[k] = arr
        elif k in _FLOAT_KEYS:
            final_data[k] = np.asarray(v, dtype=float)
        else:
            final_data[k] = np.asarray(v)
    return final_data
