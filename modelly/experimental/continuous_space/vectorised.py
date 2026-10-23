"""Whole-population operations on a continuous space.

``neighbors_within`` on the space answers "who is near whom" with one KD-tree.
The two helpers here complete the vectorised step: ``pairs_within`` returns the
same neighbour relation as index pairs, ready for ``np.add.at`` or ``bincount``
aggregation, and ``move_all`` writes every agent's new position in one call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from modelly.experimental.continuous_space.continuous_space import (
        ContinuousSpace,
    )


def pairs_within(
    space: ContinuousSpace, radius: float
) -> tuple[np.ndarray, np.ndarray]:
    """Every unordered pair of agents within ``radius``, as two row arrays ``(i, j)``.

    Rows index ``space.agent_positions`` and ``space.active_agents``; ``i < j``
    and each pair appears once. On a torus the tree is periodic.
    """
    from scipy.spatial import cKDTree  # noqa: PLC0415 - scipy is heavy

    positions = space.agent_positions
    if positions.shape[0] == 0:
        empty = np.empty(0, dtype=np.intp)
        return empty, empty
    if space.torus:
        positions = np.mod(positions - space.dimensions[:, 0], space.size)
        tree = cKDTree(positions, boxsize=space.size)
    else:
        tree = cKDTree(positions)
    pairs = tree.query_pairs(radius, output_type="ndarray")
    return pairs[:, 0], pairs[:, 1]


def difference_vectors(
    space: ContinuousSpace, i: np.ndarray, j: np.ndarray
) -> np.ndarray:
    """The vector from agent ``i`` to agent ``j`` for each pair, torus-corrected."""
    positions = space.agent_positions
    delta = positions[j] - positions[i]
    if space.torus:
        size = space.size
        delta = np.mod(delta + size / 2, size) - size / 2
    return delta


def move_all(space: ContinuousSpace, positions: np.ndarray) -> None:
    """Set every agent's position at once; wraps on a torus, clips otherwise."""
    positions = np.asarray(positions, dtype=float)
    low = space.dimensions[:, 0]
    if space.torus:
        positions = np.mod(positions - low, space.size) + low
    else:
        positions = np.clip(positions, low, space.dimensions[:, 1])
    space.agent_positions[:] = positions
