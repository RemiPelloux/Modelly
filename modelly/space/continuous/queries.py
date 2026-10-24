"""Neighbour queries on a continuous space: radius, k-nearest, all pairs."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import ArrayLike

if TYPE_CHECKING:
    from modelly.core.agent import Agent


class NeighborQueriesMixin:
    """Queries built on ``calculate_distances`` and the position array.

    Relies on the host providing ``active_agents``, ``agent_positions``,
    ``dimensions``, ``size``, ``torus``, ``_neighbors_cache`` and
    ``calculate_distances``.
    """

    def get_agents_in_radius(
        self, point: ArrayLike, radius: float | int = 1
    ) -> tuple[list, np.ndarray]:
        """Return the agents and their distances within a radius for the point."""
        distances, agents = self.calculate_distances(point)
        logical = distances <= radius
        hits = np.flatnonzero(logical).tolist()
        return [agents[i] for i in hits], distances[logical]

    def neighbors_within(self, radius: float | int) -> dict[Agent, list[Agent]]:
        """Return, for every agent, the other agents within ``radius`` of it.

        One KD-tree is built from the positions as they are now and queried for
        the whole population in a single call, which is O(n log n) instead of the
        O(n²) of asking each agent in turn. On a torus the tree is periodic, so
        neighbours across the wrap are found. Use it at the start of a step for a
        simultaneous update: every agent then sees the same snapshot of positions.

        The result is cached on the positions' content, so asking again before any
        agent moves costs a hash of the position array instead of a new tree.

        Returns:
            dict mapping each agent to a list of its neighbours (itself excluded).
        """
        agents = self.active_agents
        if not agents:
            return {}
        positions = self.agent_positions
        key = (radius, len(agents), hash(positions.tobytes()))
        cached = self._neighbors_cache
        if cached is not None and cached[0] == key:
            return cached[1]
        from scipy.spatial import cKDTree  # noqa: PLC0415 - scipy is heavy

        if self.torus:
            positions = np.mod(positions - self.dimensions[:, 0], self.size)
            tree = cKDTree(positions, boxsize=self.size)
        else:
            tree = cKDTree(positions)
        hits = tree.query_ball_point(positions, radius)
        lists = {
            agent: [agents[j] for j in indices if j != i]
            for i, (agent, indices) in enumerate(zip(agents, hits))
        }
        self._neighbors_cache = (key, lists)
        return lists

    def get_k_nearest_agents(
        self, point: ArrayLike, k: int = 1
    ) -> tuple[list, np.ndarray]:
        """Return the k nearest agents and their distances to the point.

        Notes:
            This method returns exactly k agents, ignoring ties. In case of ties, the
            earlier an agent is inserted the higher it will rank.

            If fewer than k agents are present in the space, all agents are returned
            and a UserWarning is emitted to indicate that the requested k could not be
            satisfied. If the space is empty or k <= 0, an empty result is returned
            without a warning.

        """
        dists, agents = self.calculate_distances(point)
        n = len(dists)
        # Handle empty space or invalid k
        if n == 0 or k <= 0:
            return [], np.array([])

        # If fewer agents exist than requested, warn and return all available agents
        if k > n:
            warnings.warn(
                f"Requested k={k} nearest agents but only {n} agent(s) are present in the space. "
                f"Returning all {n} agent(s).",
                UserWarning,
                stacklevel=2,
            )
            k = n

        # np.argpartition expects zero-based index (k-1) and returns the indices of the k smallest distances
        indices = np.argpartition(dists, k - 1)[:k]
        agents = [agents[i] for i in indices]
        return agents, dists[indices]
