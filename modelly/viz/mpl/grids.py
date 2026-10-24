"""Draw cell grids (orthogonal, hexagonal and Voronoi) with their agents."""

from collections.abc import Callable
from itertools import pairwise

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.patches import Polygon

from modelly.space import VoronoiGrid
from modelly.viz.mpl.agent_data import collect_agent_data
from modelly.viz.mpl.layers import (
    ROW_SPACING_FACTOR,
    HexGrid,
    OrthogonalGrid,
    _get_hexmesh,
)
from modelly.viz.mpl.scatter import _scatter

# A marker fills about this many points across the longest side of the space.
MARKER_SPAN_POINTS = 180
# Fraction of the data range added as padding on each side of the axes.
PADDING_DIVISOR = 20
# Cell centres sit on integers, so cell edges are half a unit away.
HALF_CELL = 0.5
# Decimals kept when de-duplicating shared hexagon edges.
EDGE_ROUNDING_DECIMALS = 6


def draw_orthogonal_grid(
    space: OrthogonalGrid,
    agent_portrayal: Callable,
    ax: Axes | None = None,
    draw_grid: bool = True,
    **kwargs,
):
    """Visualize a orthogonal grid.

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

    # gather agent data
    s_default = (MARKER_SPAN_POINTS / max(space.width, space.height)) ** 2
    arguments = collect_agent_data(space, agent_portrayal, default_size=s_default)

    # further styling
    ax.set_xlim(-HALF_CELL, space.width - HALF_CELL)
    ax.set_ylim(-HALF_CELL, space.height - HALF_CELL)

    # plot the agents
    _scatter(ax, arguments, **kwargs)

    if draw_grid:
        # Draw grid lines
        for x in np.arange(-HALF_CELL, space.width - HALF_CELL, 1):
            ax.axvline(x, color="gray", linestyle=":")
        for y in np.arange(-HALF_CELL, space.height - HALF_CELL, 1):
            ax.axhline(y, color="gray", linestyle=":")

    return ax


def draw_hex_grid(
    space: HexGrid,
    agent_portrayal: Callable,
    ax: Axes | None = None,
    draw_grid: bool = True,
    **kwargs,
):
    """Visualize a hex grid.

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

    # gather data
    s_default = (MARKER_SPAN_POINTS / max(space.width, space.height)) ** 2
    arguments = collect_agent_data(space, agent_portrayal, default_size=s_default)

    # Parameters for hexagon grid
    size = 1.0
    _set_hex_limits(ax, space, size)

    loc = arguments["loc"].astype(float)
    # Calculate hexagon centers for agents if agents are present and plot them.
    if loc.size > 0:
        _to_hex_centres(loc, size)
        arguments["loc"] = loc

        # plot the agents
        _scatter(ax, arguments, **kwargs)

    if draw_grid:
        ax.add_collection(_hexmesh_lines(space.width, space.height))

    return ax


def _to_hex_centres(loc, size):
    """Map grid coordinates to hexagon centres, in place."""
    x_spacing = np.sqrt(3) * size
    y_spacing = ROW_SPACING_FACTOR * size
    loc[:, 0] = loc[:, 0] * x_spacing + ((loc[:, 1] - 1) % 2) * (x_spacing / 2)
    loc[:, 1] = loc[:, 1] * y_spacing


def _set_hex_limits(ax, space, size):
    """Set plot limits that perfectly contain the hexagonal grid."""
    x_spacing = np.sqrt(3) * size
    y_spacing = ROW_SPACING_FACTOR * size

    # Calculate proper bounds that account for the full hexagon width and height
    x_max = space.width * x_spacing + (space.height % 2) * (x_spacing / 2)
    y_max = space.height * y_spacing

    # Add padding that accounts for the hexagon points
    x_padding = (
        size * np.sqrt(3) / 2
    )  # Distance from center to rightmost point of hexagon
    y_padding = size  # Distance from center to topmost point of hexagon

    # Determined through physical testing.
    ax.set_xlim(-2 * x_padding, x_max + x_padding)
    ax.set_ylim(-2 * y_padding, y_max + y_padding)


def _hexmesh_lines(width, height):
    """Return the hexmesh as a LineCollection of its unique edges."""
    edges = set()

    # Generate edges for each hexagon
    hexagons = _get_hexmesh(width, height)
    for vertices in hexagons:
        # Edge logic, connecting each vertex to the next
        for v1, v2 in pairwise([*vertices, vertices[0]]):
            # Sort vertices to ensure consistent edge representation and avoid duplicates.
            edge = tuple(
                sorted(
                    [
                        tuple(np.round(v1, EDGE_ROUNDING_DECIMALS)),
                        tuple(np.round(v2, EDGE_ROUNDING_DECIMALS)),
                    ]
                )
            )
            edges.add(edge)

    return LineCollection(edges, linestyle=":", color="black", linewidth=1, alpha=1)


def draw_voronoi_grid(
    space: VoronoiGrid,
    agent_portrayal: Callable,
    ax: Axes | None = None,
    draw_grid: bool = True,
    **kwargs,
):
    """Visualize a voronoi grid.

    Args:
        space: the space to visualize
        agent_portrayal: a callable that is called with the agent and returns a AgentPortrayalStyle
        ax: a Matplotlib Axes instance. If none is provided a new figure and ax will be created using plt.subplots
        draw_grid: whether to draw the grid or not
        kwargs: additional keyword arguments passed to ax.scatter

    Returns:
        Returns the Axes object with the plot drawn onto it.

    ``agent_portrayal`` is called with an agent and should return a AgentPortrayalStyle. Valid fields in this object are "color",
    "size", "marker", "zorder", alpha, linewidths, and edgecolors. Other field are ignored and will result in a user warning.

    """
    if ax is None:
        _, ax = plt.subplots()

    x_min, x_max, y_min, y_max = _centroid_bounds(space)

    width = x_max - x_min
    x_padding = width / PADDING_DIVISOR
    height = y_max - y_min
    y_padding = height / PADDING_DIVISOR

    s_default = (MARKER_SPAN_POINTS / max(width, height)) ** 2
    arguments = collect_agent_data(space, agent_portrayal, default_size=s_default)

    ax.set_xlim(x_min - x_padding, x_max + x_padding)
    ax.set_ylim(y_min - y_padding, y_max + y_padding)

    _scatter(ax, arguments, **kwargs)

    if draw_grid:
        ax.add_collection(_voronoi_mesh(space.all_cells.cells))
    return ax


def _centroid_bounds(space):
    """Return (x_min, x_max, y_min, y_max) of the Voronoi centroids."""
    x_list = [i[0] for i in space.centroids_coordinates]
    y_list = [i[1] for i in space.centroids_coordinates]
    return min(x_list), max(x_list), min(y_list), max(y_list)


def _voronoi_mesh(cells):
    """Return the Voronoi cells as a PatchCollection of dotted outlines."""
    patches = []
    for cell in cells:
        patch = Polygon(cell.properties["polygon"])
        patches.append(patch)
    mesh = PatchCollection(
        patches, edgecolor="k", facecolor=(1, 1, 1, 0), linestyle="dotted", lw=1
    )
    return mesh
