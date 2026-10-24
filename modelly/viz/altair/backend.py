# noqa: D100
from collections.abc import Callable

import altair as alt
import numpy as np

import modelly
from modelly.space import (
    OrthogonalMooreGrid,
    OrthogonalVonNeumannGrid,
)
from modelly.viz.altair.agent_data import (
    AGENT_DATA_KEYS,
    MARKER_TO_SHAPE,
    style_defaults,
    style_from_dict,
    to_arrays,
    unsupported_marker,
    warn_dict_portrayal,
)
from modelly.viz.altair.backend_charts import (
    add_tooltip_columns,
    agent_encodings,
    agent_frame,
    fill_encoding,
    layer_matches_space,
    property_layer_chart,
)
from modelly.viz.render.backend import AbstractRenderer

OrthogonalGrid = OrthogonalMooreGrid | OrthogonalVonNeumannGrid
HexGrid = modelly.space.HexGrid
Network = modelly.space.Network


class AltairBackend(AbstractRenderer):
    """Altair-based renderer for Modelly spaces.

    This module provides an Altair-based renderer for visualizing Modelly model spaces,
    agents, and property layers with interactive charting capabilities.
    """

    def initialize_canvas(self) -> None:
        """Initialize the Altair canvas."""
        self._canvas = None

    def draw_structure(self, **kwargs) -> alt.Chart:
        """Draw the space structure using Altair.

        Args:
            **kwargs: Additional arguments passed to the space drawer.
            Checkout respective `SpaceDrawer` class on details how to pass **kwargs.

        Returns:
            alt.Chart: The Altair chart representing the space structure.
        """
        return self.space_drawer.draw_altair(**kwargs)

    # Over the 25-line body limit on purpose (guidelines §11.3): the loop runs once
    # per agent on every render; splitting it would add a call per agent.
    def collect_agent_data(
        self, space, agent_portrayal: Callable, default_size: float | None = None
    ):
        """Collect plotting data for all agents in the space for Altair.

        Args:
            space: The Modelly space containing agents.
            agent_portrayal: Callable that returns AgentPortrayalStyle for each agent.
            default_size: Default marker size if not specified in portrayal.

        Returns:
            dict: Dictionary containing agent plotting data arrays.
        """
        arguments = {key: [] for key in AGENT_DATA_KEYS}
        style_fields = style_defaults()
        fallback_size = (
            default_size if default_size is not None else style_fields.get("size")
        )
        default_color, default_marker, default_zorder, default_alpha, default_width = (
            style_fields.get(key)
            for key in ("color", "marker", "zorder", "alpha", "linewidths")
        )
        # Warn only once per call instead of once per agent
        dict_portrayal_warned = False

        for agent in space.agents:
            portray_input = agent_portrayal(agent)
            if isinstance(portray_input, dict):
                if not dict_portrayal_warned:
                    warn_dict_portrayal()
                    dict_portrayal_warned = True
                position = self._get_agent_pos(agent, space)
                aps = style_from_dict(portray_input, position, style_fields)
            else:
                aps = portray_input
                if aps.x is None and aps.y is None:
                    aps.x, aps.y = self._get_agent_pos(agent, space)

            arguments["loc"].append((aps.x, aps.y))
            arguments["size"].append(
                aps.size if aps.size is not None else fallback_size
            )
            arguments["color"].append(
                aps.color if aps.color is not None else default_color
            )
            arguments["tooltip"].append(aps.tooltip)
            # Map marker to Altair shape if defined, else use raw marker
            raw_marker = aps.marker if aps.marker is not None else default_marker
            shape_value = MARKER_TO_SHAPE.get(raw_marker, raw_marker)
            if shape_value is None:
                shape_value = unsupported_marker(raw_marker)
            arguments["shape"].append(shape_value)
            arguments["order"].append(
                aps.zorder if aps.zorder is not None else default_zorder
            )
            arguments["opacity"].append(
                aps.alpha if aps.alpha is not None else default_alpha
            )
            arguments["stroke"].append(aps.edgecolors)
            arguments["strokeWidth"].append(
                aps.linewidths if aps.linewidths is not None else default_width
            )
            # FIXME: Make filled user-controllable
            arguments["filled"].append(True)

        return to_arrays(arguments)

    def draw_agents(
        self, arguments, chart_width: int = 450, chart_height: int = 350, **kwargs
    ):
        """Draw agents using Altair backend.

        Args:
            arguments: Dictionary containing agent data arrays.
            chart_width: Width of the chart.
            chart_height: Height of the chart.
            **kwargs: Additional keyword arguments for customization.
            Checkout respective `SpaceDrawer` class on details how to pass **kwargs.

        Returns:
            alt.Chart: The Altair chart representing the agents, or None if no agents.
        """
        if arguments["loc"].size == 0:
            return None

        df = agent_frame(arguments)
        # FIXME: Add more parameters to kwargs
        title = kwargs.pop("title", "")
        xlabel = kwargs.pop("xlabel", "")
        ylabel = kwargs.pop("ylabel", "")
        # Tooltip list for interactivity
        tooltip_list = add_tooltip_columns(df, arguments["tooltip"])
        # Handle custom colormapping
        cmap = kwargs.pop("cmap", "viridis")
        vmin = kwargs.pop("vmin", None)
        vmax = kwargs.pop("vmax", None)
        fill = fill_encoding(df, cmap, vmin, vmax)
        limits = self.space_drawer.get_viz_limits()
        encodings = agent_encodings(df, (xlabel, ylabel), limits, fill)
        return (
            alt.Chart(df)
            .mark_point()
            .encode(**encodings, tooltip=tooltip_list)
            .properties(title=title, width=chart_width, height=chart_height)
        )

    def draw_property_layer(
        self,
        space,
        property_layers: dict[str, np.ndarray],
        property_layer_portrayal: Callable,
        chart_width: int = 450,
        chart_height: int = 350,
    ):
        """Draw property layers using Altair backend.

        Args:
            space: The Modelly space object containing the property layers.
            property_layers: A dictionary mapping property_layer names to numpy arrays.
            property_layer_portrayal: A function that returns PropertyLayerStyle
                that contains the visualization parameters.
            chart_width: The width of the chart.
            chart_height: The height of the chart.

        Returns:
            alt.Chart: A tuple containing the base chart and the color bar chart.
        """
        main_charts = []
        for layer_name, layer in property_layers.items():
            if layer_name == "empty":
                continue
            portrayal = property_layer_portrayal(layer_name)
            if portrayal is None:
                continue

            data = layer.astype(float) if layer.dtype == bool else layer
            if not layer_matches_space(space, layer_name, data):
                continue

            current_chart = property_layer_chart(
                layer_name, data, portrayal, (chart_width, chart_height)
            )
            if current_chart is not None:
                main_charts.append(current_chart)

        base = alt.layer(*main_charts).resolve_scale(color="independent")
        return base
