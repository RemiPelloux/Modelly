"""Space rendering component for SolaraViz, driven by a SpaceRenderer."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any

import altair as alt
import pandas as pd
import solara

from modelly.viz.render.renderer import SpaceRenderer
from modelly.viz.utils import update_counter

if TYPE_CHECKING:
    from modelly.core.model import Model

_EMPTY_CHART_WIDTH = 450
_EMPTY_CHART_HEIGHT = 350
_VIEW_STROKE_WIDTH = 1.5


def create_space_component(renderer: SpaceRenderer):
    """Create a space visualization component for the given renderer."""

    def SpaceVisualizationComponent(model: Model):
        """Component that renders the model's space using the provided renderer."""
        return SpaceRendererComponent(model, renderer)

    return SpaceVisualizationComponent


def _clear_matplotlib_canvas(renderer: SpaceRenderer) -> None:
    """Remove the previously drawn artists and colorbars from the matplotlib canvas."""
    # Clear the previous plotted data and agents
    all_artists = [
        renderer.canvas.lines[:],
        renderer.canvas.collections[:],
        renderer.canvas.patches[:],
        renderer.canvas.images[:],
        renderer.canvas.artists[:],
    ]

    # Remove duplicate colorbars from the canvas
    for cbar in renderer.backend_renderer._active_colorbars:
        cbar.remove()
    renderer.backend_renderer._active_colorbars.clear()

    # Chain them together into a single iterable
    for artist in itertools.chain.from_iterable(all_artists):
        artist.remove()


def _render_matplotlib_space(renderer: SpaceRenderer, viz_dependencies) -> None:
    """Redraw the space on the matplotlib canvas and display the figure."""
    _clear_matplotlib_canvas(renderer)

    if renderer.space_mesh:
        renderer.draw_structure()
    if renderer.agent_mesh:
        renderer.draw_agents()
    if renderer.property_layer_mesh:
        renderer.draw_property_layer()

    if renderer.post_process and not renderer._post_process_applied:
        renderer.post_process(renderer.canvas)
        renderer._post_process_applied = True

    solara.FigureMatplotlib(
        renderer.canvas.get_figure(),
        format="png",
        bbox_inches="tight",
        dependencies=viz_dependencies,
    )


def _layer_altair_charts(charts):
    """Combine the space charts into one chart, or an empty chart when there are none."""
    if not charts:
        # If no charts are available, return an empty chart
        return (
            alt.Chart(pd.DataFrame())
            .mark_point()
            .properties(width=_EMPTY_CHART_WIDTH, height=_EMPTY_CHART_HEIGHT)
        )
    if len(charts) == 1:
        return charts[0]
    return alt.layer(*charts).resolve_axis(x="independent", y="independent")


def _render_altair_space(renderer: SpaceRenderer) -> None:
    """Draw the space charts with Altair and display the layered chart."""
    structure = renderer.draw_structure() if renderer.space_mesh else None
    agents = renderer.draw_agents() if renderer.agent_mesh else None
    props = renderer.draw_property_layer() if renderer.property_layer_mesh else None

    spatial_charts_list = [chart for chart in [structure, props, agents] if chart]
    final_chart = _layer_altair_charts(spatial_charts_list)

    if renderer.post_process:
        final_chart = renderer.post_process(final_chart)

    final_chart = final_chart.configure_view(
        stroke="black", strokeWidth=_VIEW_STROKE_WIDTH
    )

    solara.FigureAltair(final_chart, on_click=None, on_hover=None)


@solara.component
def SpaceRendererComponent(
    model: Model,
    renderer: SpaceRenderer,
    # FIXME: Manage dependencies properly
    dependencies: list[Any] | None = None,
):
    """Render the space of a model using a SpaceRenderer.

    Args:
        model (Model): The model whose space is to be rendered.
        renderer: A SpaceRenderer instance to render the model's space.
        dependencies (list[any], optional): List of dependencies for the component.
    """
    update_counter.get()

    # update renderer's space according to the model's space/grid
    renderer.space = getattr(model, "grid", getattr(model, "space", None))

    viz_dependencies = [update_counter.value]
    if dependencies:
        viz_dependencies.extend(dependencies)

    if renderer.backend == "matplotlib":
        _render_matplotlib_space(renderer, viz_dependencies)
    else:
        _render_altair_space(renderer)
    return None
