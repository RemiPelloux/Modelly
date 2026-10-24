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

from modelly.space.base import DiscreteSpace
from modelly.space.cells.agents import (
    CellAgent,
    FixedAgent,
    Grid2DMovingAgent,
    HexGridMovingAgent,
)
from modelly.space.cells.cell import Cell
from modelly.space.cells.collection import CellCollection
from modelly.space.cells.index import CellIndex
from modelly.space.cells.occupancy import NO_MATCH, Occupancy, claim
from modelly.space.grid.grids import (
    Grid,
    HexGrid,
    OrthogonalMooreGrid,
    OrthogonalVonNeumannGrid,
)
from modelly.space.network import Network
from modelly.space.voronoi import VoronoiGrid

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
