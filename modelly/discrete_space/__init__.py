"""Cell spaces for active, property-rich spatial modeling in Modelly.

Cell spaces extend Modelly's spatial modeling capabilities by making the space itself active -
each position (cell) can have properties and behaviors rather than just containing agents.
This enables more sophisticated environmental modeling and agent-environment interactions.

Key components:
- Cells: Active positions that can have properties and contain agents
- CellAgents: Agents that understand how to interact with cells
- Spaces: Different cell organization patterns (grids, networks, etc.)

This is particularly useful for models where the environment plays an active role,
like resource growth, pollution diffusion, or infrastructure networks. The cell
space system is experimental and under active development.
"""

from modelly.discrete_space.cell import Cell
from modelly.discrete_space.cell_agent import (
    CellAgent,
    FixedAgent,
    Grid2DMovingAgent,
    HexGridMovingAgent,
)
from modelly.discrete_space.cell_collection import CellCollection
from modelly.discrete_space.cell_index import CellIndex
from modelly.discrete_space.discrete_space import DiscreteSpace
from modelly.discrete_space.grid import (
    Grid,
    HexGrid,
    OrthogonalMooreGrid,
    OrthogonalVonNeumannGrid,
)
from modelly.discrete_space.network import Network
from modelly.discrete_space.occupancy import NO_MATCH, Occupancy, claim
from modelly.discrete_space.voronoi import VoronoiGrid

__all__ = [
    "NO_MATCH",
    "Cell",
    "CellAgent",
    "CellCollection",
    "CellIndex",
    "DiscreteSpace",
    "FixedAgent",
    "Grid",
    "Grid2DMovingAgent",
    "HexGrid",
    "HexGridMovingAgent",
    "Network",
    "Occupancy",
    "OrthogonalMooreGrid",
    "OrthogonalVonNeumannGrid",
    "VoronoiGrid",
    "claim",
]
