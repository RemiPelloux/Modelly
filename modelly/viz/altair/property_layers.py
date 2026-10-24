"""Altair charts and colorbars for the property layers of a space."""

import warnings
from dataclasses import dataclass

import altair as alt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb

_RGB_MAX = 255
_COLORBAR_HEIGHT = 20
_COLORBAR_TICK_COUNT = 11
_TICK_THICKNESS = 2
_TICK_SIZE = 8
_TICK_OFFSET = 2
_LABEL_FONT_SIZE = 10
_LABEL_OFFSET = 10
_TITLE_FONT_SIZE = 12
_TITLE_OFFSET = 40
_COLORBAR_PADDING = 50
# Warnings raised here are attributed to the caller of chart_property_layers
_CALLER_STACKLEVEL = 3


@dataclass
class _Layer:
    """One property layer, ready to chart."""

    name: str
    df: pd.DataFrame
    alpha: float
    vmin: float
    vmax: float
    colorbar: bool


def _prepare_layer(space, layer_name: str, layer, portrayal: dict) -> _Layer:
    """Validate a layer against the space and resolve its portrayal options."""
    data = layer.astype(float) if layer.dtype == bool else layer

    if (space.width, space.height) != data.shape:
        warnings.warn(
            f"Layer {layer_name} dimensions ({data.shape}) do not match space dimensions ({space.width}, {space.height}).",
            UserWarning,
            stacklevel=_CALLER_STACKLEVEL,
        )
    alpha = portrayal.get("alpha", 1)
    vmin = portrayal.get("vmin", np.min(data))
    vmax = portrayal.get("vmax", np.max(data))
    colorbar = portrayal.get("colorbar", True)

    # Prepare data for Altair (convert 2D array to a long-form DataFrame)
    df = pd.DataFrame(
        {
            "x": np.repeat(np.arange(data.shape[0]), data.shape[1]),
            "y": np.tile(np.arange(data.shape[1]), data.shape[0]),
            "value": data.flatten(),
        }
    )
    return _Layer(layer_name, df, alpha, vmin, vmax, colorbar)


def _rgba_mapper(layer: _Layer, color):
    """Return a function mapping a data value to an RGBA color scaled by its magnitude."""
    vmin, vmax, alpha = layer.vmin, layer.vmax, layer.alpha

    def apply_rgba(val):
        """Map a data value to an RGBA string whose opacity grows with the value."""
        # Normalize value to range [0,1] and clamp
        normalized = max(0, min((val - vmin) / (vmax - vmin), 1))

        # Scale opacity by alpha parameter
        opacity = normalized * alpha

        # Convert color to RGB components
        rgb_color = to_rgb(color)
        r = int(rgb_color[0] * _RGB_MAX)
        g = int(rgb_color[1] * _RGB_MAX)
        b = int(rgb_color[2] * _RGB_MAX)

        return f"rgba({r}, {g}, {b}, {opacity:.2f})"

    return apply_rgba


def _color_layer_chart(layer: _Layer, color, chart_size: tuple) -> alt.Chart:
    """Chart a layer as a single color whose opacity follows the values."""
    chart_width, chart_height = chart_size
    df = layer.df
    # Apply color mapping to each value in the dataset
    df["color"] = df["value"].apply(_rgba_mapper(layer, color))

    return (
        alt.Chart(df)
        .mark_rect()
        .encode(
            x=alt.X("x:O", axis=None),
            y=alt.Y("y:O", axis=None),
            fill=alt.Fill("color:N", scale=None),
        )
        .properties(width=chart_width, height=chart_height, title=layer.name)
    )


def _colormap_layer_chart(layer: _Layer, cmap, chart_size: tuple) -> alt.Chart:
    """Chart a layer through a named colormap."""
    chart_width, chart_height = chart_size
    cmap_scale = alt.Scale(scheme=cmap, domain=[layer.vmin, layer.vmax])

    return (
        alt.Chart(layer.df)
        .mark_rect(opacity=layer.alpha)
        .encode(
            x=alt.X("x:O", axis=None),
            y=alt.Y("y:O", axis=None),
            color=alt.Color(
                "value:Q",
                scale=cmap_scale,
                title=layer.name,
                legend=alt.Legend(title=layer.name) if layer.colorbar else None,
            ),
        )
        .properties(width=chart_width, height=chart_height)
    )


def _gradient_endpoints(layer: _Layer, color) -> tuple[str, str]:
    """Return the transparent and the solid (alpha) RGBA ends of the gradient."""
    # Extract RGB components from base color
    rgb_color = to_rgb(color)
    r_int = int(rgb_color[0] * _RGB_MAX)
    g_int = int(rgb_color[1] * _RGB_MAX)
    b_int = int(rgb_color[2] * _RGB_MAX)

    # Define gradient endpoints
    min_color = f"rgba({r_int},{g_int},{b_int},0)"
    max_color = f"rgba({r_int},{g_int},{b_int},{layer.alpha:.2f})"
    return min_color, max_color


def _gradient_bar(layer: _Layer, color, colorbar_width, chart_width) -> alt.Chart:
    """Draw the colorbar's transparent-to-solid linear gradient."""
    min_color, max_color = _gradient_endpoints(layer, color)
    # Create dataframe for gradient visualization
    df_gradient = pd.DataFrame({"x": [0, 1], "y": [0, 1]})
    gradient = alt.Gradient(
        gradient="linear",
        stops=[
            alt.GradientStop(color=min_color, offset=0),
            alt.GradientStop(color=max_color, offset=1),
        ],
        x1=0,
        x2=1,  # Horizontal gradient
        y1=0,
        y2=0,  # Keep y constant
    )
    return (
        alt.Chart(df_gradient)
        .mark_rect(
            x=0, y=0, width=colorbar_width, height=_COLORBAR_HEIGHT, color=gradient
        )
        .encode(
            x=alt.value(chart_width / 2),  # Center colorbar
            y=alt.value(0),
        )
        .properties(width=colorbar_width, height=_COLORBAR_HEIGHT)
    )


def _colorbar_axis(layer: _Layer, colorbar_width) -> tuple[alt.Chart, alt.Chart]:
    """Draw the colorbar's tick marks and the value labels below them."""
    # Create evenly distributed tick values
    axis_values = np.linspace(layer.vmin, layer.vmax, _COLORBAR_TICK_COUNT)
    tick_positions = np.linspace(0, colorbar_width, _COLORBAR_TICK_COUNT)

    # Prepare data for axis and labels
    axis_data = pd.DataFrame({"value": axis_values, "x": tick_positions})

    axis_chart = (
        alt.Chart(axis_data)
        .mark_tick(thickness=_TICK_THICKNESS, size=_TICK_SIZE)
        .encode(x=alt.X("x:Q", axis=None), y=alt.value(_COLORBAR_HEIGHT - _TICK_OFFSET))
    )
    text_labels = (
        alt.Chart(axis_data)
        .mark_text(baseline="top", fontSize=_LABEL_FONT_SIZE, dy=0)
        .encode(
            x=alt.X("x:Q"),
            text=alt.Text("value:Q", format=".1f"),
            y=alt.value(_COLORBAR_HEIGHT + _LABEL_OFFSET),
        )
    )
    return axis_chart, text_labels


def _colorbar_title(layer_name: str, colorbar_width) -> alt.Chart:
    """Draw the colorbar's bold title."""
    return (
        alt.Chart(pd.DataFrame([{"text": layer_name}]))
        .mark_text(
            fontSize=_TITLE_FONT_SIZE,
            fontWeight="bold",
            baseline="bottom",
            align="center",
        )
        .encode(
            text="text:N",
            x=alt.value(colorbar_width / 2),
            y=alt.value(_COLORBAR_HEIGHT + _TITLE_OFFSET),
        )
    )


def _colorbar_chart(layer: _Layer, color, chart_width) -> alt.Chart:
    """Build the full colorbar (gradient, ticks, labels and title) for a color layer."""
    colorbar_width = chart_width
    colorbar_chart = _gradient_bar(layer, color, colorbar_width, chart_width)
    axis_chart, text_labels = _colorbar_axis(layer, colorbar_width)
    title = _colorbar_title(layer.name, colorbar_width)

    # Combine all colorbar components
    return alt.layer(colorbar_chart, axis_chart, text_labels, title).properties(
        width=colorbar_width, height=_COLORBAR_HEIGHT + _COLORBAR_PADDING
    )


def _stack_colorbar(bar_chart, combined_colorbar):
    """Stack a new colorbar below the previous ones."""
    if bar_chart is None:
        return combined_colorbar
    return (
        alt.vconcat(bar_chart, combined_colorbar)
        .resolve_scale(color="independent")
        .configure_view(stroke=None)
    )


def chart_property_layers(space, property_layer_portrayal, chart_width, chart_height):
    """Creates Property Layers in the Altair Components.

    Args:
        space: the ContinuousSpace instance
        property_layer_portrayal: Dictionary of property_layer portrayal specifications
        chart_width: width of the agent chart to maintain consistency with the property_layer charts
        chart_height: height of the agent chart to maintain consistency with the property_layer charts
    Returns:
        Altair Chart
    """
    property_layers = space.property_layers
    chart_size = (chart_width, chart_height)
    base = None
    bar_chart = None
    for layer_name, portrayal in property_layer_portrayal.items():
        layer_data = property_layers.get(layer_name, None)
        if layer_data is None:
            continue

        layer = _prepare_layer(space, layer_name, layer_data, portrayal)
        if "color" in portrayal:
            chart = _color_layer_chart(layer, portrayal["color"], chart_size)
            # Add colorbar if specified in portrayal
            if layer.colorbar:
                colorbar = _colorbar_chart(layer, portrayal["color"], chart_width)
                bar_chart = _stack_colorbar(bar_chart, colorbar)
        elif "colormap" in portrayal:
            cmap = portrayal.get("colormap", "viridis")
            chart = _colormap_layer_chart(layer, cmap, chart_size)
        else:
            raise ValueError(
                f"Property Layer {layer_name} portrayal must include 'color' or 'colormap'."
            )
        base = alt.layer(chart, base) if base is not None else chart
    return base, bar_chart
