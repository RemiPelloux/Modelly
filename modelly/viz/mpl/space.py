"""Helper functions for drawing modelly spaces with matplotlib.

These functions are used by the provided matplotlib components, but can also be used to quickly visualize
a space with matplotlib for example when creating a mp4 of a movie run or when needing a figure
for a paper.

"""

from collections.abc import Callable

from matplotlib import pyplot as plt
from matplotlib.axes import Axes

import modelly
from modelly.space import (
    OrthogonalMooreGrid,
    OrthogonalVonNeumannGrid,
    VoronoiGrid,
)
from modelly.space.continuous import ContinuousSpace
from modelly.viz.mpl.agent_data import (
    _coerce_color_array,
    _to_numpy_argument_array,
    collect_agent_data,
)
from modelly.viz.mpl.continuous import draw_continuous_space
from modelly.viz.mpl.grids import (
    draw_hex_grid,
    draw_orthogonal_grid,
    draw_voronoi_grid,
)
from modelly.viz.mpl.layers import _get_hexmesh, draw_property_layers
from modelly.viz.mpl.network import draw_network
from modelly.viz.mpl.scatter import (
    CORRECTION_FACTOR_MARKER_ZOOM,
    DEFAULT_MARKER_SIZE,
    _get_zoom_factor,
    _scatter,
)

OrthogonalGrid = OrthogonalMooreGrid | OrthogonalVonNeumannGrid
HexGrid = modelly.space.HexGrid
Network = modelly.space.Network

__all__ = [
    "CORRECTION_FACTOR_MARKER_ZOOM",
    "DEFAULT_MARKER_SIZE",
    "HexGrid",
    "Network",
    "OrthogonalGrid",
    "_coerce_color_array",
    "_get_hexmesh",
    "_get_zoom_factor",
    "_scatter",
    "_to_numpy_argument_array",
    "collect_agent_data",
    "draw_continuous_space",
    "draw_hex_grid",
    "draw_network",
    "draw_orthogonal_grid",
    "draw_property_layers",
    "draw_space",
    "draw_voronoi_grid",
]


def draw_space(
    space,
    agent_portrayal: Callable,
    property_layer_portrayal: Callable | None = None,
    ax: Axes | None = None,
    **space_drawing_kwargs,
):
    """Draw a Matplotlib-based visualization of the space.

    Args:
        space: the space of the modelly model
        agent_portrayal: A callable that returns a AgnetPortrayalStyle specifying how to show the agent
        property_layer_portrayal: A callable that returns a PropertyLayerStyle specifying how to show the property layer
        ax: the axes upon which to draw the plot
        space_drawing_kwargs: any additional keyword arguments to be passed on to the underlying function for drawing the space.

    Returns:
        Returns the Axes object with the plot drawn onto it.

    ``agent_portrayal`` is called with an agent and should return a AgentPortrayalStyle. Valid fields in this object are "color",
    "size", "marker", "zorder", alpha, linewidths, and edgecolors. Other field are ignored and will result in a user warning.

    """
    if ax is None:
        _, ax = plt.subplots()

    # https://stackoverflow.com/questions/67524641/convert-multiple-isinstance-checks-to-structural-pattern-matching
    match space:
        # order matters here given the class structure of old-style grid spaces
        case modelly.space.HexGrid():
            draw_hex_grid(space, agent_portrayal, ax=ax, **space_drawing_kwargs)
        case OrthogonalMooreGrid() | OrthogonalVonNeumannGrid():
            draw_orthogonal_grid(space, agent_portrayal, ax=ax, **space_drawing_kwargs)
        case modelly.space.Network():
            draw_network(space, agent_portrayal, ax=ax, **space_drawing_kwargs)
        case ContinuousSpace():
            draw_continuous_space(space, agent_portrayal, ax=ax)
        case VoronoiGrid():
            draw_voronoi_grid(space, agent_portrayal, ax=ax)
        case _:
            raise ValueError(f"Unknown space type: {type(space)}")

    if property_layer_portrayal:
        draw_property_layers(space, property_layer_portrayal, ax=ax)

    return ax
