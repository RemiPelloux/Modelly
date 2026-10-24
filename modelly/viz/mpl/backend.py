# noqa: D100
import warnings

import numpy as np
from matplotlib.figure import Figure
from matplotlib.offsetbox import OffsetImage
from PIL import Image

import modelly
from modelly.space import (
    OrthogonalMooreGrid,
    OrthogonalVonNeumannGrid,
)
from modelly.space.base import DiscreteSpace, space_agents
from modelly.viz.mpl.agent_data import (
    portrayal_style_defaults,
    rows_to_arguments,
    snapshot_style,
    style_from_dict,
    warn_dict_portrayal,
)
from modelly.viz.mpl.layers import (
    add_layer_colorbar,
    draw_hex_layer,
    draw_orthogonal_layer,
    layer_style,
)
from modelly.viz.mpl.scatter import (
    ScatterData,
    add_image_artists,
    is_image_marker,
    scatter_by_zorder,
    validate_edge_arguments,
    zoom_factor,
)
from modelly.viz.render.backend import AbstractRenderer

OrthogonalGrid = OrthogonalMooreGrid | OrthogonalVonNeumannGrid
HexGrid = modelly.space.HexGrid


CORRECTION_FACTOR_MARKER_ZOOM = 0.01
_IGNORED_MSG = "The following keys were ignored: "


class MatplotlibBackend(AbstractRenderer):
    """Matplotlib-based renderer for Modelly spaces.

    Provides visualization capabilities using Matplotlib for rendering
    space structures, agents, and property layers.
    """

    def __init__(self, space_drawer):
        """Initialize the Matplotlib backend.

        Args:
            space_drawer: An instance of a SpaceDrawer class that handles
                the drawing of the space structure.
        """
        super().__init__(space_drawer)

        self._active_colorbars = []

    def initialize_canvas(self, ax=None):
        """Initialize the matplotlib canvas.

        Args:
            ax (matplotlib.axes.Axes, optional): Existing axes to use.
                If None, creates new figure and axes.
        """
        if ax is None:
            fig = Figure(constrained_layout=True)
            ax = fig.add_subplot()
            self.fig = fig
        self.ax = ax

    def draw_structure(self, **kwargs):
        """Draw the space structure using matplotlib.

        Args:
            **kwargs: Additional arguments passed to the space drawer.
            Checkout respective `SpaceDrawer` class on details on how to pass ``**kwargs``.

        Returns:
            The matplotlib axes with the drawn structure.
        """
        return self.space_drawer.draw_matplotlib(self.ax, **kwargs)

    def collect_agent_data(self, space, agent_portrayal, default_size=None):
        """Collect plotting data for all agents in the space.

        Args:
            space: The Modelly space containing agents.
            agent_portrayal (Callable): Function that returns AgentPortrayalStyle for each agent.
            default_size (float, optional): Default marker size if not specified in portrayal.

        Returns:
            dict: Dictionary containing agent plotting data arrays.
        """
        style_fields = portrayal_style_defaults()
        fallback_size = default_size or style_fields.get("size")
        dict_portrayal_warned = False  # warn once per call, not once per agent
        rows = []
        for agent in _live_agents(space):
            portray_input = agent_portrayal(agent)
            if isinstance(portray_input, dict):
                if not dict_portrayal_warned:
                    warn_dict_portrayal()
                    dict_portrayal_warned = True
                position = self._get_agent_pos(agent, space)
                aps = style_from_dict(
                    portray_input, position, style_fields, _IGNORED_MSG
                )
            else:
                aps = portray_input
                if aps.x is None and aps.y is None:  # Set defaults if not provided
                    aps.x, aps.y = self._get_agent_pos(agent, space)
                if aps.tooltip is not None:
                    _warn_tooltip_ignored()
            rows.append((aps.size or fallback_size, *snapshot_style(aps)))
        return rows_to_arguments(rows)

    def _get_zoom_factor(self, ax, img):
        """Calculate zoom factor only once and cache the result."""
        return zoom_factor(ax, img, CORRECTION_FACTOR_MARKER_ZOOM)

    def draw_agents(self, arguments, **kwargs):
        """Draw agents on the backend's axes - optimized version.

        Args:
            arguments: Dictionary containing agent data arrays.
            **kwargs: Additional keyword arguments for customization.
            Checkout respective `SpaceDrawer` class on details on how to pass ``**kwargs``.

        Returns:
            matplotlib.axes.Axes: The Matplotlib Axes with the agents drawn upon it.
        """
        if arguments["loc"].size == 0:
            return None

        data = _scatter_data(arguments, kwargs)
        validate_edge_arguments(arguments, kwargs)
        image_markers, regular_markers = _split_markers(data.marker)

        self.ax.get_figure().canvas.draw()

        for mark in image_markers:
            self._draw_image_marker(mark, data)
        for mark in regular_markers:
            scatter_by_zorder(self.ax, mark, data.marker == mark, data)

        return self.ax

    def _draw_image_marker(self, mark, data: ScatterData):
        """Draw the agents whose marker is this image, one image per marker size."""
        image = Image.open(mark)
        base_zoom = self._get_zoom_factor(self.ax, image)
        mask_marker = data.marker == mark

        for m_size in np.unique(data.size[mask_marker]):
            im = OffsetImage(image, zoom=base_zoom * m_size)
            im.image.axes = self.ax
            size_marker_mask = mask_marker & (data.size == m_size)
            add_image_artists(self.ax, im, size_marker_mask, data)

    def draw_property_layer(self, space, property_layers, property_layer_portrayal):
        """Draw property layers using matplotlib backend.

        Args:
            space: The Modelly space object.
            property_layers (dict): Dictionary of property layers to visualize.
            property_layer_portrayal (Callable): Function that returns PropertyLayerStyle.

        Returns:
            tuple: (matplotlib.axes.Axes, colorbar) - The matplotlib axes and colorbar objects.
        """
        # Draw each layer
        for layer_name, layer in property_layers.items():
            if layer_name == "empty":
                continue

            portrayal = property_layer_portrayal(layer_name)

            if portrayal is None:
                continue

            data = layer.astype(float) if layer.dtype == bool else layer

            if not _layer_shape_matches(space, layer_name, data):
                continue

            style = _backend_layer_style(layer_name, portrayal, data)
            self._draw_layer(space, data, style)

            # Add colorbar if requested
            cbar = None
            if portrayal.colorbar:
                cbar = add_layer_colorbar(self.ax, style)
                self._active_colorbars.append(cbar)
        return self.ax, cbar

    def _draw_layer(self, space, data, style):
        """Draw one property layer of an orthogonal or hex grid."""
        if isinstance(space, OrthogonalGrid):
            draw_orthogonal_layer(self.ax, data, style)
        elif isinstance(space, HexGrid):
            hexagons = self.space_drawer.hexagons
            draw_hex_layer(self.ax, hexagons, data.T.ravel(), style)
        else:
            raise NotImplementedError(
                f"Property Layer visualization not implemented for {type(space)}"
            )


def _live_agents(space):
    """Return the agents of the space without building an AgentSet."""
    # Iterate the live agents directly: space.agents would build a weak
    # AgentSet of the whole population for every frame.
    return space_agents(space) if isinstance(space, DiscreteSpace) else space.agents


def _scatter_data(arguments, kwargs):
    """Pop loc, marker and zorder from the agent data; alpha and s stay as arguments."""
    loc = arguments.pop("loc")
    return ScatterData(
        loc_x=loc[:, 0],
        loc_y=loc[:, 1],
        marker=arguments.pop("marker"),
        zorder=arguments.pop("zorder"),
        alpha=arguments["alpha"],
        size=arguments["s"],
        scatter_args=arguments,
        kwargs=kwargs,
    )


def _split_markers(marker):
    """Separate the image markers from the regular ones."""
    image_markers = set()
    regular_markers = set()
    for mark in set(marker):
        if is_image_marker(mark):
            image_markers.add(mark)
        else:
            regular_markers.add(mark)
    return image_markers, regular_markers


def _warn_tooltip_ignored():
    """Warn that tooltips only work with the Altair backend."""
    warnings.warn(
        "The 'tooltip' attribute in AgentPortrayalStyle is "
        "only supported by the Altair backend. "
        "Tooltips will be ignored when using the Matplotlib backend.",
        UserWarning,
        stacklevel=3,  # the caller of collect_agent_data()
    )


def _layer_shape_matches(space, layer_name, data):
    """Return whether the layer matches the space; warn when it does not."""
    if (space.width, space.height) != data.shape:
        warnings.warn(
            f"Layer {layer_name} dimensions ({data.shape}) "
            f"don't match space dimensions ({space.width}, {space.height})",
            UserWarning,
            stacklevel=3,  # the caller of draw_property_layer()
        )
        return False
    return True


def _backend_layer_style(layer_name, portrayal, data):
    """Resolve the style; unset vmin/vmax fall back to the data range."""
    vmin = portrayal.vmin if portrayal.vmin is not None else np.min(data)
    vmax = portrayal.vmax if portrayal.vmax is not None else np.max(data)
    return layer_style(
        layer_name,
        portrayal,
        (vmin, vmax),
        f"Property Layer {layer_name} must include 'color' or 'colormap'",
    )
