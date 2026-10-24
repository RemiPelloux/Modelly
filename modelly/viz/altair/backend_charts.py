"""Chart builders behind AltairBackend.draw_agents and AltairBackend.draw_property_layer."""

import warnings

import altair as alt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb

# strokeWidth is drawn on a [0, 1] scale, so widths are divided by this factor first
_STROKE_WIDTH_SCALE = 10
_SIZE_DOMAIN_MAX = 50
_RGB_MAX = 255
# Warnings raised here are attributed to the caller of AltairBackend.draw_property_layer
_CALLER_STACKLEVEL = 3


def _viz_colors(df: pd.DataFrame) -> tuple[list, list]:
    """Return the fill and stroke color of each agent, honouring ``is_filled``."""
    fill_colors = []
    stroke_colors = []
    for i in range(len(df)):
        filled = df["is_filled"][i]
        main_color = df["original_color"][i]
        stroke_spec = (
            df["original_stroke"][i]
            if isinstance(df["original_stroke"][i], str)
            else None
        )
        if filled:
            fill_colors.append(main_color)
            stroke_colors.append(stroke_spec)
        else:
            fill_colors.append(None)
            stroke_colors.append(main_color)
    return fill_colors, stroke_colors


def agent_frame(arguments: dict) -> pd.DataFrame:
    """Build the agents' DataFrame, including the fill and stroke colors to draw."""
    # To get a continuous scale for color the domain should be between [0, 1]
    # that's why changing the the domain of strokeWidth beforehand.
    stroke_width = [data / _STROKE_WIDTH_SCALE for data in arguments["strokeWidth"]]
    df = pd.DataFrame(
        {
            "x": arguments["loc"][:, 0],
            "y": arguments["loc"][:, 1],
            "size": arguments["size"],
            "shape": arguments["shape"],
            "opacity": arguments["opacity"],
            "strokeWidth": stroke_width,
            "original_color": arguments["color"],
            "is_filled": arguments["filled"],
            "original_stroke": arguments["stroke"],
        }
    )

    df["viz_fill_color"], df["viz_stroke_color"] = _viz_colors(df)
    return df


def add_tooltip_columns(df: pd.DataFrame, tooltips) -> list:
    """Add one column per tooltip key to ``df`` and return the sorted tooltip keys."""
    # Find ALL unique keys
    all_tooltips_key = set()
    column_data = {}

    for tooltip in tooltips:
        if tooltip:
            all_tooltips_key.update(tooltip.keys())

    if all_tooltips_key:
        # pre-build columns
        column_data = {key: [None] * len(tooltips) for key in all_tooltips_key}

    for i, tooltip in enumerate(tooltips):
        if tooltip:
            for key, value in tooltip.items():
                column_data[key][i] = value

    for key, values in column_data.items():
        df[key] = values

    return sorted(all_tooltips_key)


def fill_encoding(df: pd.DataFrame, cmap, vmin, vmax) -> alt.Fill:
    """Return a colormap fill for numeric colors, or the literal colors otherwise."""
    if pd.api.types.is_numeric_dtype(df["original_color"]):
        color_min = vmin if vmin is not None else df["original_color"].min()
        color_max = vmax if vmax is not None else df["original_color"].max()
        return alt.Fill(
            "original_color:Q",
            scale=alt.Scale(scheme=cmap, domain=[color_min, color_max]),
        )
    return alt.Fill("viz_fill_color:N", scale=None, title="Color")


def _position_encodings(labels: tuple, limits: tuple) -> dict:
    """Return the x and y encodings, scaled to the space limits."""
    xlabel, ylabel = labels
    xmin, xmax, ymin, ymax = limits
    return {
        "x": alt.X(
            "x:Q",
            title=xlabel,
            scale=alt.Scale(type="linear", domain=[xmin, xmax]),
            axis=None,
        ),
        "y": alt.Y(
            "y:Q",
            title=ylabel,
            scale=alt.Scale(type="linear", domain=[ymin, ymax]),
            axis=None,
        ),
    }


def agent_encodings(df: pd.DataFrame, labels: tuple, limits: tuple, fill) -> dict:
    """Return the encoding channels of the agent chart, in drawing order."""
    # To ensure distinct shapes according to agent portrayal
    shape_names = df["shape"].unique().tolist()
    return {
        **_position_encodings(labels, limits),
        "size": alt.Size(
            "size:Q", legend=None, scale=alt.Scale(domain=[0, _SIZE_DOMAIN_MAX])
        ),
        "shape": alt.Shape(
            "shape:N",
            scale=alt.Scale(domain=shape_names, range=shape_names),
            title="Shape",
        ),
        "opacity": alt.Opacity(
            "opacity:Q", title="Opacity", scale=alt.Scale(domain=[0, 1], range=[0, 1])
        ),
        "fill": fill,
        "stroke": alt.Stroke("viz_stroke_color:N", scale=None),
        "strokeWidth": alt.StrokeWidth("strokeWidth:Q", scale=alt.Scale(domain=[0, 1])),
    }


def layer_matches_space(space, layer_name: str, data) -> bool:
    """Return whether the layer has the space's shape, warning when it does not."""
    if (space.width, space.height) == data.shape:
        return True
    warnings.warn(
        f"Property Layer {layer_name} dimensions ({data.shape}) "
        f"don't match space dimensions ({space.width}, {space.height})",
        UserWarning,
        stacklevel=_CALLER_STACKLEVEL,
    )
    return False


def _layer_color_scale(layer_name: str, portrayal, vmin, vmax):
    """Return ``(color scale, opacity)`` for a property layer portrayal."""
    if portrayal.color:
        # For a single color gradient, we define the range from transparent to solid.
        rgb = to_rgb(portrayal.color)
        r, g, b = (int(c * _RGB_MAX) for c in rgb)

        min_color = f"rgba({r},{g},{b},0)"
        max_color = f"rgba({r},{g},{b},{portrayal.alpha})"
        return alt.Scale(range=[min_color, max_color], domain=[vmin, vmax]), 1

    if portrayal.colormap:
        return alt.Scale(
            scheme=portrayal.colormap, domain=[vmin, vmax]
        ), portrayal.alpha

    raise ValueError(
        f"Property Layer {layer_name} portrayal must include 'color' or 'colormap'."
    )


def _layer_frame(data) -> pd.DataFrame:
    """Convert a 2D property layer into a long-form DataFrame."""
    return pd.DataFrame(
        {
            "x": np.repeat(np.arange(data.shape[0]), data.shape[1]),
            "y": np.tile(np.arange(data.shape[1] - 1, -1, -1), data.shape[0]),
            "value": data.flatten(),
        }
    )


def property_layer_chart(layer_name: str, data, portrayal, chart_size: tuple):
    """Draw one property layer as a heatmap of rectangles."""
    chart_width, chart_height = chart_size
    vmin = portrayal.vmin if portrayal.vmin is not None else np.min(data)
    vmax = portrayal.vmax if portrayal.vmax is not None else np.max(data)

    df = _layer_frame(data)
    color_scale, opacity = _layer_color_scale(layer_name, portrayal, vmin, vmax)
    legend = (
        alt.Legend(title=layer_name, orient="bottom") if portrayal.colorbar else None
    )
    return (
        alt.Chart(df)
        .mark_rect(opacity=opacity)
        .encode(
            x=alt.X("x:O", axis=None),
            y=alt.Y("y:O", axis=None),
            color=alt.Color(
                "value:Q", scale=color_scale, title=layer_name, legend=legend
            ),
        )
        .properties(width=chart_width, height=chart_height)
    )
