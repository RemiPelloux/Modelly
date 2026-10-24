"""Space rendering module for Modelly visualizations.

This module provides functionality to render Modelly model spaces with different
backends, supporting various space types and visualization components.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from modelly.viz.components import PropertyLayerStyle

import modelly
from modelly.viz.render.altair_canvas import redraw_altair_canvas
from modelly.viz.render.drawers.base import Network
from modelly.viz.render.legacy_args import (
    apply_deprecated_agent_args,
    apply_deprecated_layer_portrayal,
    apply_deprecated_render_args,
    apply_deprecated_structure_args,
)
from modelly.viz.render.portrayal import as_property_layer_callable
from modelly.viz.render.space_setup import (
    make_backend,
    make_space_drawer,
    map_coordinates,
)


class SpaceRenderer:
    """Renders Modelly spaces using different visualization backends.

    Supports multiple space types and backends for flexible visualization
    of agent-based models.
    """

    def __init__(
        self,
        model: modelly.Model,
        backend: Literal["matplotlib", "altair"] | None = "matplotlib",
    ):
        """Initialize the space renderer.

        Args:
            model (modelly.Model): The Modelly model to render.
            backend (Literal["matplotlib", "altair"] | None): The visualization backend to use.
        """
        self.space = getattr(model, "grid", getattr(model, "space", None))

        self.space_drawer = self._get_space_drawer()

        self.space_mesh = None
        self.agent_mesh = None
        self.property_layer_mesh = None

        self.draw_agent_kwargs = {}
        self.draw_space_kwargs = {}

        self.agent_portrayal = None
        self.property_layer_portrayal = None

        self.post_process_func = None
        # Keep track of whether post-processing has been applied
        # to avoid multiple applications on the same axis.
        self._post_process_applied = False

        self.backend = backend
        self.backend_renderer = make_backend(backend, self.space_drawer)
        self.backend_renderer.initialize_canvas()

    def _get_space_drawer(self):
        """Get appropriate space drawer based on space type.

        Returns:
            Space drawer instance for the model's space type.

        Raises:
            ValueError: If the space type is not supported.
        """
        return make_space_drawer(self.space)

    def _map_coordinates(self, arguments):
        """Map agent coordinates to appropriate space coordinates.

        Args:
            arguments (dict): Dictionary containing agent data with coordinates.

        Returns:
            dict: Dictionary with mapped coordinates appropriate for the space type.
        """
        return map_coordinates(self.space, self.space_drawer, arguments)

    def setup_structure(self, **kwargs) -> SpaceRenderer:
        """Setup the space structure without drawing.

        Args:
            **kwargs: Additional keyword arguments for the setup function. For ContinuousSpace,
                you may pass ``viz_dims=(i, j)`` to select which two dimensions are projected
                to x/y.
            Checkout respective `SpaceDrawer` class on details on how to pass ``**kwargs``.

        Returns:
            SpaceRenderer: The current instance for method chaining.
        """
        self.draw_space_kwargs = kwargs
        self.space_mesh = None

        return self

    def setup_agents(self, agent_portrayal: Callable, **kwargs) -> SpaceRenderer:
        """Setup agents on the space without drawing.

        Args:
            agent_portrayal (Callable): Function that takes an agent and returns AgentPortrayalStyle.
            **kwargs: Additional keyword arguments for the setup function.
            Checkout respective `SpaceDrawer` class on details on how to pass ``**kwargs``.

        Returns:
            SpaceRenderer: The current instance for method chaining.
        """
        self.agent_portrayal = agent_portrayal
        self.draw_agent_kwargs = kwargs
        self.agent_mesh = None

        return self

    def setup_property_layer(
        self, property_layer_portrayal: Callable | dict | PropertyLayerStyle
    ) -> SpaceRenderer:
        """Setup property layers on the space without drawing.

        Args:
            property_layer_portrayal (Callable | dict | PropertyLayerStyle): A PropertyLayerStyle,
                a function that produces a PropertyLayerStyle instance, or a dictionary specifying portrayal parameters.

        Returns:
            SpaceRenderer: The current instance for method chaining.
        """
        self.property_layer_portrayal = property_layer_portrayal
        self.property_layer_mesh = None

        return self

    def draw_structure(self, **kwargs):
        """Draw the space structure.

        Args:
            **kwargs: (Deprecated) Additional keyword arguments for drawing.
                    Use setup_structure() instead.

        Returns:
            The visual representation of the space structure.
        """
        apply_deprecated_structure_args(self, kwargs)

        # Network-specific: the space instance is replaced on every model reset.
        # If the drawer still references the old space its layout positions belong
        # to the previous (now stale) graph.  Rebuild before drawing edges so that
        # the structure is always consistent with the current space.
        if (
            isinstance(self.space, Network)
            and self.space_drawer.space is not self.space
        ):
            self.space_drawer = self._get_space_drawer()
            self.backend_renderer.space_drawer = self.space_drawer

        self.space_mesh = self.backend_renderer.draw_structure(**self.draw_space_kwargs)
        return self.space_mesh

    def draw_agents(self, agent_portrayal=None, **kwargs):
        """Draw agents on the space.

        Args:
            agent_portrayal: (Deprecated) Function that takes an agent and returns AgentPortrayalStyle.
                            Use setup_agents() instead.
            **kwargs: (Deprecated) Additional keyword arguments for drawing.

        Returns:
            The visual representation of the agents.
        """
        apply_deprecated_agent_args(self, agent_portrayal, kwargs)

        # Prepare data for agent plotting
        arguments = self.backend_renderer.collect_agent_data(
            self.space, self.agent_portrayal, default_size=self.space_drawer.s_default
        )
        arguments = self._map_coordinates(arguments)

        self.agent_mesh = self.backend_renderer.draw_agents(
            arguments, **self.draw_agent_kwargs
        )
        return self.agent_mesh

    def draw_property_layer(self, property_layer_portrayal=None):
        """Draw property layers on the space.

        Args:
            property_layer_portrayal: (Deprecated) A PropertyLayerStyle, a function that produces
            a PropertyLayerStyle instance, or a dictionary specifying portrayal parameters.
            Use setup_property_layer() instead.

        Returns:
            The visual representation of the property layers.

        Raises:
            Exception: If no property layers are found on the space.
        """
        apply_deprecated_layer_portrayal(self, property_layer_portrayal)

        property_layers = self.space.property_layers
        self.property_layer_portrayal = as_property_layer_callable(
            self.property_layer_portrayal
        )

        number_of_props = sum(1 for layer in property_layers if layer != "empty")
        if number_of_props < 1:
            raise Exception("No property layers were found on the space.")

        self.property_layer_mesh = self.backend_renderer.draw_property_layer(
            self.space, property_layers, self.property_layer_portrayal
        )
        return self.property_layer_mesh

    def render(self, agent_portrayal=None, property_layer_portrayal=None, **kwargs):
        """Render the complete space with structure, agents, and property layers.

        Args:
            agent_portrayal: (Deprecated) Function for agent portrayal. Use setup_agents() instead.
            property_layer_portrayal: (Deprecated) Function for property layer portrayal. Use setup_property_layer() instead.
            **kwargs: (Deprecated) Additional keyword arguments.
        """
        if (
            agent_portrayal is not None
            or property_layer_portrayal is not None
            or kwargs
        ):
            apply_deprecated_render_args(
                self, agent_portrayal, property_layer_portrayal, kwargs
            )

        if self.space_mesh is None:
            self.draw_structure()
        if self.agent_mesh is None and self.agent_portrayal is not None:
            self.draw_agents()
        if (
            self.property_layer_mesh is None
            and self.property_layer_portrayal is not None
        ):
            self.draw_property_layer()

        return self

    @property
    def canvas(self):
        """Get the current canvas object.

        Returns:
            The backend-specific canvas object.
        """
        if self.backend == "matplotlib":
            ax = self.backend_renderer.ax
            if ax is None:
                self.backend_renderer.initialize_canvas()
            return ax

        elif self.backend == "altair":
            return redraw_altair_canvas(self)

    @property
    def post_process(self):
        """Get the current post-processing function.

        Returns:
            Callable | None: The post-processing function, or None if not set.
        """
        return self.post_process_func

    @post_process.setter
    def post_process(self, func: Callable | None):
        """Set the post-processing function.

        Args:
            func (Callable | None): Function to apply post-processing to the canvas.
                Should accept the canvas object as its first argument.
        """
        self.post_process_func = func
