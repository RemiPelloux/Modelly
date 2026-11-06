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


class _SpaceFigure:
    """One figure of a model's space kept across frames: only the agents are redrawn.

    ``draw(model)`` draws what ``space_figure`` draws. While the model's space is the
    same object, the grid lines, hexagons, cells or network drawn the first time stay
    on the axes and only the agents' artists are replaced; a different space (a
    restored checkpoint, another model) starts a new figure. Studio keeps one per
    session, and ``save_animation`` one per file.

    Args:
        figsize: Width and height in inches.
        dpi: Pixels per inch.
    """

    def __init__(
        self, figsize: tuple[float, float] = DEFAULT_FIGSIZE, dpi: int = DEFAULT_DPI
    ) -> None:
        """Start without a figure: the first ``draw`` makes it."""
        self.figsize = figsize
        self.dpi = dpi
        self.figure: Figure | None = None
        self._space: Any = None
        self._renderer: SpaceRenderer | None = None
        self._structure: set[Any] = set()
        self._checked: tuple[Any, bool] = (None, False)

    def can_draw(self, model: Model) -> bool:
        """``can_draw(model)``, checked once per space object."""
        space = model_space(model)
        if space is None:
            return False
        if space is not self._checked[0]:
            self._checked = (space, can_draw(model))
        return self._checked[1]

    def draw(self, model: Model, agent_portrayal: Callable | None = None) -> Figure:
        """The figure of ``model``'s space and agents, as ``space_figure`` draws it.

        Raises:
            ValueError: If the model has no space ``SpaceRenderer`` supports.
        """
        portrayal = agent_portrayal or ClassColours()
        space = model_space(model)
        if self._renderer is None or self.figure is None or space is not self._space:
            self.figure = Figure(
                figsize=self.figsize, dpi=self.dpi, layout="constrained"
            )
            self._renderer = SpaceRenderer(model, backend="matplotlib")
            axes = self.figure.add_subplot()
            self._renderer.backend_renderer.initialize_canvas(axes)
            self._renderer.draw_structure()
            self._structure = set(axes.get_children())
            self._space = space
        renderer = self._renderer
        axes = renderer.backend_renderer.ax
        # Back to the position a new figure starts from: the constrained layout then
        # places the axes exactly where it places them on a new figure.
        axes.set_subplotspec(axes.get_subplotspec())
        remove_agents(axes, self._structure)
        renderer.setup_agents(portrayal)
        renderer.draw_agents()
        return self.figure


def remove_agents(axes: Any, keep: set[Any]) -> None:
    """Remove every drawn artist of ``axes`` that is not in ``keep``."""
    drawn = [*axes.collections, *axes.images, *axes.artists, *axes.lines, *axes.patches]
    for artist in drawn:
        if artist not in keep:
            artist.remove()


def figure_pixels(figure: Figure) -> np.ndarray:
    """The figure rendered to an ``(height, width, 3)`` uint8 RGB array."""
    canvas = FigureCanvasAgg(figure)
    canvas.draw()
    return np.asarray(canvas.buffer_rgba())[..., :RGB_CHANNELS].copy()


__all__ = ["can_draw", "figure_pixels", "model_space", "space_figure"]
