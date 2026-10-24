"""Draw network spaces with their agents."""

from collections.abc import Callable

import networkx as nx
from matplotlib import pyplot as plt
from matplotlib.axes import Axes

import modelly
from modelly.viz.mpl.agent_data import collect_agent_data
from modelly.viz.mpl.grids import MARKER_SPAN_POINTS, PADDING_DIVISOR
from modelly.viz.mpl.scatter import _scatter

Network = modelly.space.Network

NETWORK_NODE_SIZE = 10


def draw_network(
    space: Network,
    agent_portrayal: Callable,
    ax: Axes | None = None,
    draw_grid: bool = True,
    **kwargs,
):
    """Visualize a network space.

    Args:
        space: the space to visualize
        agent_portrayal: a callable that is called with the agent and returns a AgentPortrayalStyle
        ax: a Matplotlib Axes instance. If none is provided a new figure and ax will be created using plt.subplots
        draw_grid: whether to draw the grid
        kwargs: additional keyword arguments passed to ax.scatter

    Returns:
        Returns the Axes object with the plot drawn onto it.

    ``agent_portrayal`` is called with an agent and should return a AgentPortrayalStyle. Valid fields in this object are "color",
    "size", "marker", "zorder", alpha, linewidths, and edgecolors. Other field are ignored and will result in a user warning.

    """
    if ax is None:
        _, ax = plt.subplots()

    pos = _node_positions(space)
    bounds = _node_bounds(pos)
    xmin, xmax, ymin, ymax = bounds

    width = xmax - xmin
    height = ymax - ymin

    # gather agent data
    s_default = (MARKER_SPAN_POINTS / max(width, height)) ** 2
    arguments = collect_agent_data(space, agent_portrayal, default_size=s_default)

    arguments["loc"] = arguments["loc"].astype(float)

    _set_network_limits(ax, bounds)

    if draw_grid:
        _draw_network_grid(ax, space, pos)

    # plot the agents
    _scatter(ax, arguments, **kwargs)

    return ax


def _node_positions(space):
    """Fetch the node positions natively from the Model Cells."""
    pos = {}
    for node_id, cell in space._cells.items():
        pos_val = getattr(cell, "position", getattr(cell, "_position", None))
        if pos_val is not None:
            pos[node_id] = pos_val
    return pos


def _node_bounds(pos):
    """Return (xmin, xmax, ymin, ymax) of the node positions."""
    x, y = list(zip(*pos.values())) if pos else ([0], [0])
    return min(x), max(x), min(y), max(y)


def _set_network_limits(ax, bounds):
    """Hide the axis and set padded limits around the nodes."""
    xmin, xmax, ymin, ymax = bounds
    x_padding = (xmax - xmin) / PADDING_DIVISOR
    y_padding = (ymax - ymin) / PADDING_DIVISOR
    ax.set_axis_off()
    ax.set_xlim(xmin=xmin - x_padding, xmax=xmax + x_padding)
    ax.set_ylim(ymin=ymin - y_padding, ymax=ymax + y_padding)


def _draw_network_grid(ax, space, pos):
    """Draw the underlying grid (edges and empty nodes) below the agents."""
    nodes = nx.draw_networkx_nodes(
        space.G, pos, ax=ax, alpha=0.5, node_size=NETWORK_NODE_SIZE, node_color="gray"
    )
    edges = nx.draw_networkx_edges(space.G, pos, ax=ax, alpha=0.5, style="--")

    if nodes:
        nodes.set_zorder(0)
    if edges:
        edges.set_zorder(0)
