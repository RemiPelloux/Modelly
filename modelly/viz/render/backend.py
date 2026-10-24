"""Abstract base class for visualization backends in Modelly.

This module provides the foundational interface for implementing various
visualization backends for Modelly agent-based models.
"""

from abc import ABC, abstractmethod

import modelly
from modelly.space import (
    DiscreteSpace,
    OrthogonalMooreGrid,
    OrthogonalVonNeumannGrid,
)

OrthogonalGrid = OrthogonalMooreGrid | OrthogonalVonNeumannGrid
HexGrid = modelly.space.HexGrid
Network = modelly.space.Network

_TOO_FEW_DIMENSIONS = "Continuous space visualization requires at least 2 dimensions"
_PROJECTION_OUT_OF_RANGE = (
    "Agent position does not have enough dimensions for the selected "
    "visualization projection"
)


def _row_placed_cell(agent, space):
    """Return the cell of an agent placed by a row column (CellIndex.track)."""
    index = space._cell_index
    if index is None:
        raise ValueError(f"{type(agent).__name__} has no cell in this space")
    return index.cell_of(agent)


class AbstractRenderer(ABC):
    """Abstract base class for visualization backends.

    This class defines the interface for rendering Modelly spaces and agents.
    For details on the methods checkout specific backend implementations.
    """

    def __init__(self, space_drawer):
        """Initialize the renderer.

        Args:
            space_drawer: Object responsible for drawing space elements. Checkout `SpaceDrawer`
            for more details on the detailed implementations of the drawing functions.
        """
        self.space_drawer = space_drawer
        self._canvas = None

    def _get_agent_pos(self, agent, space):
        """Get agent position based on space type."""
        if isinstance(space, DiscreteSpace):
            # Avoid Cell.position: it allocates a numpy array per call (hot path).
            cell = getattr(agent, "cell", None)
            if cell is None:  # placed by a row column (CellIndex.track)
                cell = _row_placed_cell(agent, space)
            position = cell._position
            return cell.coordinate if position is None else position

        pos = agent.position
        if len(pos) < 2:
            raise ValueError(_TOO_FEW_DIMENSIONS)

        i, j = (0, 1)
        viz_dims = getattr(self.space_drawer, "viz_dims", None)
        if (
            isinstance(viz_dims, tuple)
            and len(viz_dims) == 2
            and all(isinstance(dim, int) for dim in viz_dims)
        ):
            i, j = viz_dims

        try:
            return pos[i], pos[j]
        except IndexError as err:
            raise ValueError(_PROJECTION_OUT_OF_RANGE) from err

    @abstractmethod
    def initialize_canvas(self):
        """Set up the drawing canvas."""

    @abstractmethod
    def draw_structure(self, **kwargs):
        """Draw the space structure.

        Args:
            **kwargs: Structure drawing configuration options.
        """

    @abstractmethod
    def collect_agent_data(self, space, agent_portrayal, default_size=None):
        """Collect plotting data for all agents in the space.

        Args:
            space: The Modelly space containing agents.
            agent_portrayal (Callable): Function that returns AgentPortrayalStyle for each agent.
            default_size (float, optional): Default marker size if not specified in portrayal.

        Returns:
            dict: Dictionary containing agent plotting data arrays with keys:
        """

    @abstractmethod
    def draw_agents(self, arguments, **kwargs):
        """Drawing agents on space.

        Args:
            arguments (dict): Dictionary containing agent data.
            **kwargs: Additional drawing configuration options.
        """

    @abstractmethod
    def draw_property_layer(self, space, property_layers, property_layer_portrayal):
        """Draw property layers on the visualization.

        Args:
            space: The model's space object.
            property_layers (dict): Dictionary of property layers to visualize.
            property_layer_portrayal (Callable): Function that returns PropertyLayerStyle.
        """
