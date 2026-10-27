"""How a partition finds, places and removes agents in each kind of space.

``CellAdapter`` serves the cell spaces (grids and ``Network``): an agent's
location is its cell's coordinate, ghosts sit in the halo cells of the local
copy of the space, and the cells to send to a neighbour are worked out once per
radius. ``ContinuousAdapter`` serves ``ContinuousSpace``: a location is a
position, and the agents to send are those within the radius of the
neighbour's box, found again before every phase since agents move.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from modelly.core.agent import Agent
from modelly.distributed.contract import PartitionError
from modelly.distributed.kdtree import KDLayout
from modelly.space.base import DiscreteSpace
from modelly.space.continuous.space import ContinuousSpace


class CellAdapter:
    """Ghosts and migrants on a grid or a network."""

    def __init__(self, space: DiscreteSpace, layout: Any, index: int) -> None:
        """Partition ``index`` of ``layout`` over ``space``."""
        self.space, self.layout, self.index = space, layout, index
        self._borders: dict[float, dict[int, list]] = {}
        self._own: set | None = None

    @staticmethod
    def location(agent: Agent) -> Any:
        """The coordinate of the agent's cell."""
        return agent.cell.coordinate

    def located(self, agent: Agent) -> bool:
        """Whether the agent is in a cell of this space."""
        cell = getattr(agent, "cell", None)
        return cell is not None and self.space._cells.get(cell.coordinate) is cell

    def owners(self, agents: list[Agent]) -> np.ndarray:
        """The partition owning each agent's cell."""
        return np.asarray(
            self.layout.owners([a.cell.coordinate for a in agents]), dtype=np.int64
        )

    def strangers(self, agents: list[Agent]) -> list[Agent]:
        """The agents standing in cells another partition owns."""
        if self._own is None:
            cells = list(self.space._cells.values())
            owners = self.layout.owners([cell.coordinate for cell in cells])
            mine = np.flatnonzero(np.asarray(owners) == self.index).tolist()
            self._own = {cells[i] for i in mine}
        own = self._own
        return [agent for agent in agents if agent._modelly_cell not in own]

    def _border(self, radius: float) -> dict[int, list]:
        """For each neighbour, the local cells in its halo (in the space's order)."""
        layout, me, cells = self.layout, self.index, self.space._cells
        reach = math.ceil(radius)
        border = {}
        for other in sorted(layout.neighbours(me, reach)):
            halo = list(layout.halo(other, reach))
            owners = np.asarray(layout.owners(halo)).tolist()
            wanted = {c for c, owner in zip(halo, owners, strict=True) if owner == me}
            border[other] = [cell for key, cell in cells.items() if key in wanted]
        return border

    def outgoing(self, radius: float) -> dict[int, list[Agent]]:
        """For each neighbour, the local agents within ``radius`` of it."""
        if radius not in self._borders:
            self._borders[radius] = self._border(radius)
        return {
            other: [agent for cell in cells for agent in cell._agents]
            for other, cells in self._borders[radius].items()
        }

    def attach(self, agent: Agent, location: Any, ghost: bool) -> None:
        """Put ``agent`` in the cell at ``location`` (a ghost bypasses movement rules)."""
        cell = self.space._cells[location]
        if ghost:
            cell.add_agent(agent)
            agent._modelly_cell = cell
        else:
            agent.cell = cell

    @staticmethod
    def detach(agent: Agent) -> None:
        """Take ``agent`` out of its cell without calling its ``remove``."""
        agent._modelly_cell.remove_agent(agent)
        agent._modelly_cell = None


class ContinuousAdapter:
    """Ghosts and migrants in a continuous space split by a ``KDLayout``."""

    def __init__(self, space: ContinuousSpace, layout: KDLayout, index: int) -> None:
        """Box ``index`` of ``layout`` over ``space``."""
        self.space, self.layout, self.index = space, layout, index

    @staticmethod
    def location(agent: Agent) -> tuple[float, ...]:
        """The agent's position as a tuple of floats."""
        return tuple(agent.position.tolist())

    def located(self, agent: Agent) -> bool:
        """Whether the agent is in this space."""
        return getattr(agent, "space", None) is self.space

    def owners(self, agents: list[Agent]) -> np.ndarray:
        """The box owning each agent's position."""
        rows = [a._modelly_index for a in agents]
        return self.layout.owners(self.space.agent_positions[rows])

    def strangers(self, agents: list[Agent]) -> list[Agent]:
        """The agents standing in another partition's box."""
        if not agents:
            return []
        outside = np.flatnonzero(self.owners(agents) != self.index).tolist()
        return [agents[i] for i in outside]

    def outgoing(self, radius: float) -> dict[int, list[Agent]]:
        """For each other box, the local agents within ``radius`` of it."""
        agents = list(self.space.active_agents)
        positions = self.space.agent_positions
        out = {}
        for other in range(len(self.layout)):
            if other != self.index:
                near = np.flatnonzero(self.layout.near(other, positions, radius))
                if len(near):
                    out[other] = [agents[i] for i in near.tolist()]
        return out

    def attach(self, agent: Agent, location: Any, ghost: bool) -> None:
        """Add ``agent`` to the space at ``location``."""
        agent.space = self.space
        self.space._add_agent(agent)
        self.space.agent_positions[agent._modelly_index] = location

    def detach(self, agent: Agent) -> None:
        """Take ``agent`` out of the space without calling its ``remove``."""
        self.space._remove_agent(agent)
        agent._modelly_index = None
        agent.space = None


def adapter_for(space: Any, layout: Any, index: int) -> CellAdapter | ContinuousAdapter:
    """The adapter for ``space`` split by ``layout``.

    Raises:
        PartitionError: for a space or a layout the distributed run cannot split.
    """
    if isinstance(space, ContinuousSpace):
        if not isinstance(layout, KDLayout):
            raise PartitionError("a ContinuousSpace is split with partition.kd(parts)")
        return ContinuousAdapter(space, layout, index)
    if isinstance(space, DiscreteSpace):
        if isinstance(layout, KDLayout):
            raise PartitionError(
                "a cell space is split with partition.grid_blocks or partition.graph"
            )
        return CellAdapter(space, layout, index)
    raise PartitionError(
        f"cannot split a {type(space).__name__}: a partitionable model's space is a "
        "grid, a Network or a ContinuousSpace"
    )
