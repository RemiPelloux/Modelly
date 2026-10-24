"""A Continuous Space class."""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from random import Random
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import ArrayLike

from modelly.core.agent import Agent, AgentSet
from modelly.space.continuous.queries import NeighborQueriesMixin

if TYPE_CHECKING:
    from modelly.space.continuous.agents import ContinuousSpaceAgent


class ContinuousSpace[A: ContinuousSpaceAgent](NeighborQueriesMixin):
    """Continuous space where each agent can have an arbitrary position."""

    @property
    def x_min(self):  # noqa: D102
        # compatibility with solara_viz
        return self.dimensions[0, 0]

    @property
    def x_max(self):  # noqa: D102
        # compatibility with solara_viz
        return self.dimensions[0, 1]

    @property
    def y_min(self):  # noqa: D102
        # compatibility with solara_viz
        return self.dimensions[1, 0]

    @property
    def y_max(self):  # noqa: D102
        # compatibility with solara_viz
        return self.dimensions[1, 1]

    @property
    def width(self):  # noqa: D102
        # compatibility with solara_viz
        return self.size[0]

    @property
    def height(self):  # noqa: D102
        # compatibility with solara_viz
        return self.size[1]

    def __init__(
        self,
        dimensions: ArrayLike,
        torus: bool = False,
        random: Random | None = None,
        n_agents: int = 100,
    ) -> None:
        """Create a new continuous space.

        Args:
            dimensions: a numpy array like object where each row specifies the minimum and maximum value of that dimension.
            torus: boolean for whether the space wraps around or not
            random: a seeded stdlib random.Random instance
            n_agents: the expected number of agents in the space

        Internally, a numpy array is used to store the positions of all agents. This is resized if needed,
        but you can control the initial size explicitly by passing n_agents.


        """
        if random is None:
            warnings.warn(
                "Random number generator not specified, this can make models non-reproducible. Please pass a random number generator explicitly",
                UserWarning,
                stacklevel=2,
            )
            random = Random()  # noqa: MDL001 (a space takes no model: only the rng passed in seeds it)
        self.random = random

        self.dimensions: np.array = np.asanyarray(dimensions)
        self.ndims: int = self.dimensions.shape[0]

        self.size: np.array = self.dimensions[:, 1] - self.dimensions[:, 0]
        self.center: np.array = np.sum(self.dimensions, axis=1) / 2

        self.torus: bool = torus
        self._init_storage(n_agents)

    def _init_storage(self, n_agents: int) -> None:
        """Allocate the position array and the agent bookkeeping."""
        # self._agent_positions is the array containing all agent positions
        # plus potential extra empty rows
        # agent_positions is a view into _agent_positions containing only the filled rows
        self._agent_positions: np.array = np.empty(
            (n_agents, self.dimensions.shape[0]), dtype=float
        )
        # Initialize agent_positions as an empty view (zero rows) into _agent_positions.
        # This avoids copying data and ensures agent_positions always reflects the current
        # active slice of _agent_positions as agents are added or removed.
        self.agent_positions = self._agent_positions[0:0]

        # the list of agents in the space
        self.active_agents = []
        self._n_agents = 0  # the number of active agents in the space

        #  a mapping from agents to index and vice versa
        self._index_to_agent: dict[int, Agent] = {}
        # (radius, n, hash of positions) -> neighbour lists, see neighbors_within
        self._neighbors_cache: tuple[tuple, dict] | None = None

    @property
    def agents(self) -> AgentSet[A]:
        """Return an AgentSet with the agents in the space."""
        return AgentSet(self.active_agents, random=self.random)

    def _add_agent(self, agent: Agent) -> int:
        """Helper method for adding an agent to the space.

        This method manages the numpy array with the agent positions and ensuring it is
        enlarged if and when needed. It is called automatically by ContinousSpaceAgent when created.

        """
        index = self._n_agents
        self._n_agents += 1

        current_capacity = self._agent_positions.shape[0]
        if current_capacity <= index:
            # expand using pre-allocation with a growth factor
            growth_factor = 0.2
            n = max(int(current_capacity * growth_factor), 20)
            new_capacity = current_capacity + n

            new_positions = np.empty(
                (new_capacity, self.dimensions.shape[0]), dtype=float
            )
            new_positions[:current_capacity] = self._agent_positions
            self._agent_positions = new_positions

        agent._modelly_index = index
        self._index_to_agent[index] = agent

        # we want to maintain a view rather than a copy on the active agents and positions
        # this is essential for the performance of the rest of this code
        self.active_agents.append(agent)
        self.agent_positions = self._agent_positions[0 : self._n_agents]

        return index

    def _remove_agent(self, agent: Agent) -> None:
        """Remove an agent from the space.

        This method is automatically called by ContinuousSpaceAgent.remove.

        """
        index = agent._modelly_index
        last_index = self._n_agents - 1

        # If the removed agent isn't already the last one, swap the last one into its place
        if index != last_index:
            last_agent = self.active_agents[last_index]

            # Swap in active_agents list
            self.active_agents[index] = last_agent

            # Swap in numpy array
            self._agent_positions[index] = self._agent_positions[last_index]

            last_agent._modelly_index = index
            self._index_to_agent[index] = last_agent

        # Pop the last elements
        self.active_agents.pop()
        self._index_to_agent.pop(last_index, None)
        self._n_agents -= 1
        self.agent_positions = self._agent_positions[0 : self._n_agents]

    def calculate_difference_vector(self, point: np.ndarray, agents=None) -> np.ndarray:
        """Calculate the difference vector between the point and all agenents.

        Args:
            point: the point to calculate the difference vector for
            agents: the agents to calculate the difference vector of point with. By default,
                    all agents are considered.


        """
        point = np.asanyarray(point)
        positions = (
            self.agent_positions
            if agents is None
            else self._agent_positions[[a._modelly_index for a in agents]]
        )

        offset = positions - point
        if not self.torus:
            return offset

        # Across the wrap the same pair is ``size`` closer or farther; keep, per
        # component, whichever of the two has the smaller magnitude.
        wrapped = offset - np.sign(offset) * self.size
        return np.where(np.abs(offset) < np.abs(wrapped), offset, wrapped)

    def calculate_distances(
        self, point: ArrayLike, agents: Iterable[Agent] | None = None, **kwargs
    ) -> tuple[np.ndarray, list]:
        """Calculate the distance between the point and all agents.

        Args:
            point: the point to calculate the difference vector for
            agents: the agents to calculate the difference vector of point with. By default,
                    all agents are considered.
            kwargs: any additional keyword arguments are passed to scipy's cdist, which is used
                    only if torus is False. This allows for non-Euclidian distance measures.

        """
        point = np.asanyarray(point)

        if agents is None:
            positions = self.agent_positions
            agents = self.active_agents
        else:
            positions = self._agent_positions[[a._modelly_index for a in agents]]
            agents = np.asarray(agents)

        if self.torus:
            delta = np.abs(point - positions)
            delta = np.minimum(delta, self.size - delta, out=delta)

            # + is much faster than np.sum or array.sum
            dists = delta[:, 0] ** 2
            for i in range(1, self.ndims):
                dists += delta[:, i] ** 2
            dists = np.sqrt(dists)
        else:
            from scipy.spatial.distance import cdist  # noqa: PLC0415 - scipy is heavy

            dists = cdist(point[np.newaxis, :], positions, **kwargs)[0, :]
        return dists, agents

    def in_bounds(self, point: ArrayLike) -> bool:
        """Check if point is inside the bounds of the space."""
        return bool(
            (
                (np.asanyarray(point) >= self.dimensions[:, 0])
                & (point <= self.dimensions[:, 1])
            ).all()
        )

    def torus_correct(self, point: ArrayLike) -> np.ndarray:
        """Apply a torus correction to the point."""
        return self.dimensions[:, 0] + np.mod(
            np.asanyarray(point) - self.dimensions[:, 0], self.size
        )
