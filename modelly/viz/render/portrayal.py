"""Portrayal Components Module.

This module defines data structures for styling visual elements in Modelly agent-based model visualizations.
It provides user-facing classes to specify how agents and property layers should appear in the rendered space.

Classes:
1. AgentPortrayalStyle: Controls the appearance of individual agents (e.g., color, shape, size, etc.).
2. PropertyLayerStyle: Controls the appearance of background property layers (e.g., color gradients or uniform fills).

These components are designed to be passed into Modelly visualizations to customize and standardize how data is presented.

This module is the one portrayal API every backend (Matplotlib, Altair) and Modelly Studio
share: the style classes, their defaults, the conversion of legacy portrayal dicts, and
``ClassColours``, the default portrayal that colours agents by class.
"""

import warnings
from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Any

from modelly.viz.palettes import OKABE_ITO

ColorLike = str | tuple | int | float


@dataclass
class AgentPortrayalStyle:
    """Represents the visual styling options for an agent in a visualization.

    User facing component to control how agents are drawn.
    Allows specifying properties like color, size,
    marker shape, position, and other plot attributes.

    x, y are determined automatically according to the agent's type
    (normal/CellAgent) and position in the space if not manually declared.

    Example:
        >>> def agent_portrayal(agent):
        >>>     return AgentPortrayalStyle(
        >>>         x=agent.cell.coordinate[0],
        >>>         y=agent.cell.coordinate[1],
        >>>         color="red",
        >>>         marker="o",
        >>>         size=20,
        >>>         zorder=2,
        >>>         alpha=0.8,
        >>>         edgecolors="black",
        >>>         linewidths=1.5
        >>>     )
        >>>
        >>> # or for a default agent portrayal
        >>> def agent_portrayal(agent):
        >>>     return AgentPortrayalStyle()
    """

    x: float | None = None
    y: float | None = None
    color: ColorLike | None = "tab:blue"
    marker: str | None = "o"
    size: int | float | None = 50
    zorder: int | None = 1
    alpha: float | None = 1.0
    edgecolors: str | tuple | None = None
    linewidths: float | int | None = 1.0
    tooltip: dict | None = None
    # Hollow markers when False; honoured by the Altair backend only.
    filled: bool = True

    def update(self, *updates_fields: tuple[str, Any]):
        """Updates attributes from variable (field_name, new_value) tuple arguments.

        Example:
            >>> def agent_portrayal(agent):
            >>>     primary_style = AgentPortrayalStyle(color="blue", marker="^", size=10, x=agent.pos[0], y=agent.pos[1])
            >>>     if agent.type == 1:
            >>>         primary_style.update(("color", "red"), ("size", 30))
            >>>     return primary_style
        """
        for field_to_change, field_to_change_to in updates_fields:
            if hasattr(self, field_to_change):
                setattr(self, field_to_change, field_to_change_to)
            else:
                raise AttributeError(
                    f"'{type(self).__name__}' object has no attribute '{field_to_change}'"
                )

    def __post_init__(self):
        """Validate that color and size are non-negative."""
        # Tuple checks: this runs once per agent per frame, and a union type is
        # about twice as slow in isinstance.
        if isinstance(self.color, (int, float)) and self.color < 0:
            raise ValueError("Scalar color values must be non-negative")
        if isinstance(self.size, (int, float)) and self.size < 0:
            raise ValueError("Size must be a non-negative number")


# Attribute a warning to the caller of the function that called the warning helper.
CALLER_STACKLEVEL = 3
# Fields a legacy portrayal dict may set, besides the position.
DICT_STYLE_KEYS = (
    "size",
    "color",
    "marker",
    "zorder",
    "alpha",
    "edgecolors",
    "linewidths",
)


def style_defaults() -> dict[str, Any]:
    """Return the default value of every AgentPortrayalStyle field, by field name."""
    return {f.name: f.default for f in fields(AgentPortrayalStyle)}


def warn_dict_portrayal(stacklevel: int = CALLER_STACKLEVEL) -> None:
    """Warn that returning a dict from agent_portrayal is deprecated."""
    warnings.warn(
        (
            "Returning a dict from agent_portrayal is deprecated and will be removed in a future release. "
            "Please return an AgentPortrayalStyle instance instead. "
            "For more information, refer to the migration guide: "
        ),
        FutureWarning,
        stacklevel=stacklevel,
    )


def dict_to_style(
    portray_input: dict, position, style_fields: dict
) -> tuple["AgentPortrayalStyle", list[str]]:
    """Build an AgentPortrayalStyle from a legacy portrayal dict.

    Returns the style and the keys of the dict it did not use, for the caller to warn about.
    """
    dict_data = portray_input.copy()
    agent_x, agent_y = position
    styles = {key: dict_data.pop(key, style_fields.get(key)) for key in DICT_STYLE_KEYS}
    return AgentPortrayalStyle(x=agent_x, y=agent_y, **styles), list(dict_data)


class ClassColours:
    """The default portrayal: one colour per agent class, in the order classes are met.

    Any model can be drawn with it, which is what Modelly Studio does when no portrayal is
    given. The palette defaults to Okabe-Ito, which stays distinct with colour-blindness.

    Args:
        palette: The colours to cycle through, one per agent class.
        size: The marker size of every agent.
    """

    def __init__(self, palette: Sequence[str] | None = None, size: float = 50) -> None:
        """Colour agents from ``palette`` (Okabe-Ito when None)."""
        self.palette = tuple(palette or OKABE_ITO)
        self.size = size
        self.classes: dict[str, str] = {}

    def __call__(self, agent: Any) -> "AgentPortrayalStyle":
        """The style of ``agent``: its class's colour."""
        name = type(agent).__name__
        colour = self.classes.get(name)
        if colour is None:
            colour = self.palette[len(self.classes) % len(self.palette)]
            self.classes[name] = colour
        return AgentPortrayalStyle(color=colour, size=self.size)


@dataclass
class PropertyLayerStyle:
    """Represents the visual styling options for a property layer in a visualization.

    User facing component to control how property layers are drawn.
    Allows specifying properties like colormap, single color, value limits
    (vmin, vmax), transparency (alpha) and colorbar visibility.

    Note: vmin and vmax are the lower and upper bounds for the colorbar and the data is
    normalized between these values for color/colormap rendering. If they are not
    declared the values are automatically determined from the data range.

    Note: You can specify either a 'colormap' (for varying data) or a single
    'color' (for a uniform layer appearance), but not both simultaneously.

    Example:
        >>> def property_layer_portrayal(layer):
        >>>     return PropertyLayerStyle(colormap="viridis", vmin=0, vmax=100, alpha=0.5, colorbar=True)
        >>> # or for a uniform color layer
        >>> def property_layer_portrayal(layer):
        >>>     return PropertyLayerStyle(color="lightblue", alpha=0.8, colorbar=False)
    """

    colormap: str | None = None
    color: str | None = None
    alpha: float = 0.8
    colorbar: bool = True
    vmin: float | None = None
    vmax: float | None = None

    def __post_init__(self):
        """Validate that color and colormap are not simultaneously specified."""
        if self.color is not None and self.colormap is not None:
            raise ValueError("Specify either 'color' or 'colormap', not both.")
        if self.color is None and self.colormap is None:
            raise ValueError("Specify one of 'color' or 'colormap'")


def property_layer_dict_to_callable(portrayal_dict: dict[str, dict[str, Any]]):
    """Convert a legacy property_layer_portrayal dict to a PropertyLayerStyle callable.

    Args:
        portrayal_dict (dict): Dictionary with portrayal parameters per layer name.

    Returns:
        Callable: Function that returns a PropertyLayerStyle, or None for a layer
        missing from the dict.
    """

    def style_callable(layer_object: Any):
        layer_name = layer_object
        params = portrayal_dict.get(layer_name)

        _warn_dict_layer_portrayal()

        if params is None:
            return None  # Layer not specified in the dict, so skip.

        return PropertyLayerStyle(
            color=params.get("color"),
            colormap=params.get("colormap"),
            alpha=params.get("alpha", PropertyLayerStyle.alpha),
            vmin=params.get("vmin"),
            vmax=params.get("vmax"),
            colorbar=params.get("colorbar", PropertyLayerStyle.colorbar),
        )

    return style_callable


def _warn_dict_layer_portrayal():
    """Warn that the property_layer_portrayal dict is deprecated."""
    warnings.warn(
        (
            "The property_layer_portrayal dict is deprecated and will be removed in a future release. "
            "Please use a callable that returns a PropertyLayerStyle instance instead. "
            "For more information, refer to the migration guide: "
        ),
        FutureWarning,
        stacklevel=3,  # the caller of the style callable
    )


def as_property_layer_callable(portrayal):
    """Return a property layer portrayal as a callable returning PropertyLayerStyle.

    A legacy dict is converted, a PropertyLayerStyle is wrapped in a callable that
    always returns it, and anything else (already a callable) is returned as-is.
    """
    if isinstance(portrayal, dict):
        return property_layer_dict_to_callable(portrayal)
    if isinstance(portrayal, PropertyLayerStyle):
        # Capture the style instance to avoid circular reference
        style = portrayal
        return lambda _: style
    return portrayal
