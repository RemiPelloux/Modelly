"""Draw continuous spaces with their agents."""

from collections.abc import Callable

from matplotlib import pyplot as plt
from matplotlib.axes import Axes

from modelly.space.continuous import ContinuousSpace
from modelly.viz.mpl.agent_data import collect_agent_data
from modelly.viz.mpl.grids import MARKER_SPAN_POINTS, PADDING_DIVISOR
from modelly.viz.mpl.scatter import _scatter

# Dash pattern (offset, (on, off)) of the border of a toroidal space.
TORUS_BORDER_DASH = (0, (5, 10))
BORDER_LINEWIDTH = 1.5


def draw_continuous_space(
    space: ContinuousSpace, agent_portrayal: Callable, ax: Axes | None = None, **kwargs
):
    """Visualize a continuous space.

    Args:
        space: the space to visualize
        agent_portrayal: a callable that is called with the agent and returns a AgentPortrayalStyle
        ax: a Matplotlib Axes instance. If none is provided a new figure and ax will be created using plt.subplots
        kwargs: additional keyword arguments passed to ax.scatter

    Returns:
        Returns the Axes object with the plot drawn onto it.

    ``agent_portrayal`` is called with an agent and should return a AgentPortrayalStyle. Valid fields in this object are "color",
    "size", "marker", "zorder", alpha, linewidths, and edgecolors. Other field are ignored and will result in a user warning.

    """
    if ax is None:
        _, ax = plt.subplots()

    # space related setup
    width = space.x_max - space.x_min
    x_padding = width / PADDING_DIVISOR
    height = space.y_max - space.y_min
    y_padding = height / PADDING_DIVISOR

    # gather agent data
    s_default = (MARKER_SPAN_POINTS / max(width, height)) ** 2
    arguments = collect_agent_data(space, agent_portrayal, default_size=s_default)

    # further visual styling
    _style_border(ax, space.torus)

    ax.set_xlim(space.x_min - x_padding, space.x_max + x_padding)
    ax.set_ylim(space.y_min - y_padding, space.y_max + y_padding)

    # plot the agents
    _scatter(ax, arguments, **kwargs)

    return ax


def _style_border(ax, torus):
    """Draw the axes frame solid, or dashed for a toroidal space."""
    border_style = "solid" if not torus else TORUS_BORDER_DASH
    for spine in ax.spines.values():
        spine.set_linewidth(BORDER_LINEWIDTH)
        spine.set_color("black")
        spine.set_linestyle(border_style)
