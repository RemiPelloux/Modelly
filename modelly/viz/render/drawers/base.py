"""Base class and shared helpers for the space drawers."""

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

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
# Grid-line styling a LineCollection takes as axvline/axhline do (else one line each).
COLLECTION_KEYWORDS = frozenset({"color", "linestyle", "linewidth", "alpha", "zorder"})


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


def _draw_grid_lines(ax, xs, ys, line_kwargs):
    """Draw a full-height line at each of ``xs`` and a full-width one at each of ``ys``.

    Two ``LineCollection`` artists rather than one ``axvline``/``axhline`` per line, so
    a large grid draws (and redraws) quickly. Styling keywords a collection does not
    take the same way (anything outside :data:`COLLECTION_KEYWORDS`) fall back to one
    line per position, as before.
    """
    if not line_kwargs.keys() <= COLLECTION_KEYWORDS:
        for x in xs:
            ax.axvline(x, **line_kwargs)
        for y in ys:
            ax.axhline(y, **line_kwargs)
        return
    style = {
        "colors": line_kwargs.get("color"),
        "linestyles": line_kwargs.get("linestyle", "solid"),
        "linewidths": line_kwargs.get("linewidth"),
        "alpha": line_kwargs.get("alpha"),
        "zorder": line_kwargs.get("zorder", Line2D.zorder),
    }
    vertical = [((x, 0), (x, 1)) for x in xs]
    horizontal = [((0, y), (1, y)) for y in ys]
    for segments, transform in (
        (vertical, ax.get_xaxis_transform()),
        (horizontal, ax.get_yaxis_transform()),
    ):
        collection = LineCollection(segments, transform=transform, **style)
        ax.add_collection(collection, autolim=False)
