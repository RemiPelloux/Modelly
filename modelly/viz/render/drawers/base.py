"""Base class and shared helpers for the space drawers."""

import matplotlib.pyplot as plt

import modelly
from modelly.space import OrthogonalMooreGrid, OrthogonalVonNeumannGrid

OrthogonalGrid = OrthogonalMooreGrid | OrthogonalVonNeumannGrid
HexGrid = modelly.space.HexGrid
Network = modelly.space.Network

# A marker fills about this many points across the longest side of the space.
MARKER_SPAN_POINTS = 180
# Fraction of the data range added as padding on each side of the axes.
PADDING_DIVISOR = 20
DEFAULT_FIGSIZE = (8, 8)
DEFAULT_DPI = 100


class BaseSpaceDrawer:
    """Base class for all space drawers."""

    def __init__(self, space):
        """Initialize the base space drawer.

        Args:
            space: Grid/Space type to draw.
        """
        self.space = space
        self.viz_xmin = None
        self.viz_xmax = None
        self.viz_ymin = None
        self.viz_ymax = None

    def get_viz_limits(self):
        """Get visualization limits for the space.

        Returns:
            A tuple of (xmin, xmax, ymin, ymax) for visualization limits.
        """
        return (
            self.viz_xmin,
            self.viz_xmax,
            self.viz_ymin,
            self.viz_ymax,
        )

    def _set_padded_limits(self, x_range, y_range):
        """Set the default marker size and the padded limits from data ranges."""
        (x_min, x_max), (y_min, y_max) = x_range, y_range
        width = x_max - x_min
        height = y_max - y_min
        self.s_default = (
            (MARKER_SPAN_POINTS / max(width, height)) ** 2
            if width > 0 or height > 0
            else 1
        )
        self.viz_xmin = x_min - width / PADDING_DIVISOR
        self.viz_xmax = x_max + width / PADDING_DIVISOR
        self.viz_ymin = y_min - height / PADDING_DIVISOR
        self.viz_ymax = y_max + height / PADDING_DIVISOR


def axes_with_figure_kwargs(ax, draw_space_kwargs):
    """Pop figsize/dpi from the kwargs and create axes when none is given."""
    fig_kwargs = {
        "figsize": draw_space_kwargs.pop("figsize", DEFAULT_FIGSIZE),
        "dpi": draw_space_kwargs.pop("dpi", DEFAULT_DPI),
    }
    if ax is None:
        _, ax = plt.subplots(**fig_kwargs)
    return ax


def chart_properties(chart_width, chart_height, draw_chart_kwargs):
    """Return the chart properties: width, height, then the remaining kwargs."""
    chart_props = {
        "width": chart_width,
        "height": chart_height,
    }
    chart_props.update(draw_chart_kwargs)
    return chart_props


def line_mark_kwargs(draw_chart_kwargs):
    """Pop the dashed line mark styling from the kwargs, with defaults."""
    return {
        "color": draw_chart_kwargs.pop("color", "black"),
        "strokeDash": draw_chart_kwargs.pop("strokeDash", [2, 2]),
        "strokeWidth": draw_chart_kwargs.pop("strokeWidth", 1),
        "opacity": draw_chart_kwargs.pop("opacity", 0.8),
    }
