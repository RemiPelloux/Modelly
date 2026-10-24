"""Draw a model's space into a Matplotlib figure, without a GUI or a notebook.

``space_figure`` is what Modelly Studio shows, what its figure export saves and what
``modelly.viz.animation`` turns into frames: one ``SpaceRenderer`` on the Matplotlib backend,
drawn on a plain ``Figure`` (no pyplot), so it works headless on every OS.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from modelly.viz.render.portrayal import ClassColours
from modelly.viz.render.renderer import SpaceRenderer

if TYPE_CHECKING:
    from modelly.core.model import Model

DEFAULT_FIGSIZE = (5.0, 5.0)
DEFAULT_DPI = 100
RGB_CHANNELS = 3


def model_space(model: Model) -> Any:
    """The space a model draws: ``model.grid``, else ``model.space``, else None."""
    space = getattr(model, "grid", None)
    return space if space is not None else getattr(model, "space", None)


def can_draw(model: Model) -> bool:
    """Whether ``model`` has a space ``SpaceRenderer`` can draw."""
    space = model_space(model)
    if space is None:
        return False
    try:
        SpaceRenderer(model, backend="matplotlib")
    except (ValueError, TypeError, AttributeError):
        return False
    return True


def space_figure(
    model: Model,
    agent_portrayal: Callable | None = None,
    figsize: tuple[float, float] = DEFAULT_FIGSIZE,
    dpi: int = DEFAULT_DPI,
) -> Figure:
    """A new figure of the model's space and agents.

    Args:
        model: The model; its space is ``model.grid`` or ``model.space``.
        agent_portrayal: Returns an ``AgentPortrayalStyle`` per agent; ``ClassColours()``
            (one colour-blind-safe colour per agent class) when None.
        figsize: Width and height in inches.
        dpi: Pixels per inch.

    Raises:
        ValueError: If the model has no space ``SpaceRenderer`` supports.
    """
    figure = Figure(figsize=figsize, dpi=dpi, layout="constrained")
    renderer = SpaceRenderer(model, backend="matplotlib")
    renderer.backend_renderer.initialize_canvas(figure.add_subplot())
    renderer.setup_agents(agent_portrayal or ClassColours()).render()
    return figure


def figure_pixels(figure: Figure) -> np.ndarray:
    """The figure rendered to an ``(height, width, 3)`` uint8 RGB array."""
    canvas = FigureCanvasAgg(figure)
    canvas.draw()
    return np.asarray(canvas.buffer_rgba())[..., :RGB_CHANNELS].copy()


__all__ = ["can_draw", "figure_pixels", "model_space", "space_figure"]
