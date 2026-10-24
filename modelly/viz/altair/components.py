"""Altair based solara components for visualization modelly spaces."""

import warnings
from collections.abc import Callable

import altair as alt
import solara

from modelly.viz.altair.property_layers import chart_property_layers
from modelly.viz.altair.space_chart import _draw_grid
from modelly.viz.utils import update_counter

__all__ = [
    "PlotAltair",
    "SpaceAltair",
    "chart_property_layers",
    "make_altair_plot_component",
    "make_altair_space",
    "make_space_altair",
]

_PLOT_WIDTH = 450
_PLOT_HEIGHT = 350


def make_space_altair(*args, **kwargs):  # noqa: D103
    warnings.warn(
        "make_space_altair has been renamed to make_altair_space",
        FutureWarning,
        stacklevel=2,
    )
    return make_altair_space(*args, **kwargs)


def make_altair_space(
    agent_portrayal,
    property_layer_portrayal=None,
    post_process=None,
    **space_drawing_kwargs,
):
    """Create an Altair-based space visualization component.

    Args:
        agent_portrayal: Function to portray agents.
        property_layer_portrayal: Dictionary of property_layer portrayal specifications
        post_process :A user specified callable that will be called with the Chart instance from Altair. Allows for fine tuning plots (e.g., control ticks)
        space_drawing_kwargs : not yet implemented

    ``agent_portrayal`` is called with an agent and should return a dict. Valid fields in this dict are "color",
    "size", "marker", and "zorder". Other field are ignored and will result in a user warning.


    Returns:
        function: A function that creates a SpaceMatplotlib component
    """
    if agent_portrayal is None:

        def agent_portrayal(a):
            return {"id": a.unique_id}

    def MakeSpaceAltair(model):
        return SpaceAltair(
            model,
            agent_portrayal,
            property_layer_portrayal=property_layer_portrayal,
            post_process=post_process,
        )

    return MakeSpaceAltair


@solara.component
def SpaceAltair(
    model,
    agent_portrayal,
    property_layer_portrayal=None,
    dependencies: list[any] | None = None,
    post_process=None,
):
    """Create an Altair-based space visualization component.

    Returns:
        a solara FigureAltair instance
    """
    update_counter.get()
    space = getattr(model, "grid", None)
    if space is None:
        # Sometimes the space is defined as model.space instead of model.grid
        space = model.space

    chart = _draw_grid(space, agent_portrayal, property_layer_portrayal)
    # Apply post-processing if provided
    if post_process is not None:
        chart = post_process(chart)

    solara.FigureAltair(chart)


def make_altair_plot_component(
    measure: str | dict[str, str] | list[str] | tuple[str],
    post_process: Callable | None = None,
    page: int = 0,
    grid=False,
):
    """Create a plotting function for a specified measure.

    Args:
        measure (str | dict[str, str] | list[str] | tuple[str]): Measure(s) to plot.
        post_process: a user-specified callable to do post-processing called with the Axes instance.
        page: Page number where the plot should be displayed.
        grid: Bool to draw grid or not.

    Returns:
        (function, page): A tuple of a function that creates a PlotAltair component and a page number.
    """

    def MakePlotAltair(model):
        return PlotAltair(model, measure, post_process=post_process, grid=grid)

    return (MakePlotAltair, page)


def _measures_to_plot(measure) -> tuple[list, str]:
    """Return the measure names to plot and the y-axis title."""
    y_title = "Value"
    if isinstance(measure, str):
        measures_to_plot = [measure]
        y_title = measure
    elif isinstance(measure, list | tuple):
        measures_to_plot = list(measure)
    elif isinstance(measure, dict):
        measures_to_plot = list(measure.keys())
    return measures_to_plot, y_title


def _line_chart(df_long, y_title: str, grid) -> alt.Chart:
    """Draw the measures as interactive lines over the steps."""
    return (
        alt.Chart(df_long)
        .mark_line()
        .encode(
            x=alt.X("Step:Q", axis=alt.Axis(tickMinStep=1, title="Step", grid=grid)),
            y=alt.Y("Value:Q", axis=alt.Axis(title=y_title, grid=grid)),
            tooltip=["Step", "Measure", "Value"],
        )
        .properties(width=_PLOT_WIDTH, height=_PLOT_HEIGHT)
        .interactive()
    )


def _color_by_measure(chart: alt.Chart, measure) -> alt.Chart:
    """Color the lines by measure, with the user's colors when ``measure`` is a dict."""
    color_args = {}
    if isinstance(measure, dict):
        color_args["scale"] = alt.Scale(
            domain=list(measure.keys()), range=list(measure.values())
        )
    return chart.encode(color=alt.Color("Measure:N", **color_args))


@solara.component
def PlotAltair(model, measure, post_process: Callable | None = None, grid=False):
    """Create an Altair-based plot for a measure or measures.

    Args:
        model (modelly.Model): The model instance.
        measure (str | dict[str, str] | list[str] | tuple[str]): Measure(s) to plot.
            If a dict is given, keys are measure names and values are colors.
        post_process: A user-specified callable for post-processing, called
            with the Altair Chart instance.
        grid: Bool to draw grid or not.

    Returns:
        solara.FigureAltair: A component for rendering the plot.
    """
    update_counter.get()
    df = model.datacollector.get_model_vars_dataframe().reset_index()
    df = df.rename(columns={"index": "Step"})
    measures_to_plot, y_title = _measures_to_plot(measure)

    df_long = df.melt(
        id_vars=["Step"],
        value_vars=measures_to_plot,
        var_name="Measure",
        value_name="Value",
    )
    chart = _line_chart(df_long, y_title, grid)

    if len(measures_to_plot) > 0:
        chart = _color_by_measure(chart, measure)

    if post_process is not None:
        chart = post_process(chart)

    return solara.FigureAltair(chart)
