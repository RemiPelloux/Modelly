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
    style_columns,
    style_defaults,
    style_from_dict,
    to_arrays,
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
            Checkout respective `SpaceDrawer` class on details on how to pass ``**kwargs``.

        Returns:
            alt.Chart: The Altair chart representing the space structure.
        """
        return self.space_drawer.draw_altair(**kwargs)

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
        style_fields = style_defaults()
        fallback_size = (
            default_size if default_size is not None else style_fields.get("size")
        )
        styles = self._portrayal_styles(space, agent_portrayal, style_fields)
        return to_arrays(style_columns(styles, style_fields, fallback_size))

    def _portrayal_styles(
        self, space, agent_portrayal: Callable, style_fields: dict
    ) -> list:
        """Return each agent's AgentPortrayalStyle, positioned in the space."""
        # Warn only once per call instead of once per agent
        dict_portrayal_warned = False
        styles = []
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
            styles.append(aps)
        return styles

    def draw_agents(
        self, arguments, chart_width: int = 450, chart_height: int = 350, **kwargs
    ):
        """Draw agents using Altair backend.

        Args:
            arguments: Dictionary containing agent data arrays.
            chart_width: Width of the chart.
            chart_height: Height of the chart.
            **kwargs: ``title``, ``xlabel``, ``ylabel``, ``cmap``, ``vmin`` and ``vmax``
                customise the chart; any other keyword is an Altair point-mark
                property (for example ``strokeDash``) passed to ``mark_point``.
            Checkout respective `SpaceDrawer` class on details on how to pass ``**kwargs``.

        Returns:
            alt.Chart: The Altair chart representing the agents, or None if no agents.
        """
        if arguments["loc"].size == 0:
            return None

        df = agent_frame(arguments)
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
            .mark_point(**kwargs)
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
