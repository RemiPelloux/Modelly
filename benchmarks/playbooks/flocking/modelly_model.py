"""Flocking (boids) on a torus, simultaneous update, written for Modelly.

Same model as ``mesa_model.py``. The neighbour relation comes from one periodic
KD-tree query for the whole flock (``pairs_within``); the three steering terms
are pair sums scattered back to the boids with ``bincount``; the positions are
written in one call (``move_all``).
"""

from __future__ import annotations

import numpy as np

from modelly import Model
from modelly.experimental.continuous_space import (
    ContinuousSpace,
    ContinuousSpaceAgent,
    difference_vectors,
    move_all,
    pairs_within,
)


class Boid(ContinuousSpaceAgent):
    """A boid; its heading lives in the flock's ``directions`` array."""


def scatter(i, j, values, n):
    """Sum ``values`` of each pair into row i and its negation into row j."""
    out = np.empty((n, values.shape[1]))
    for axis in range(values.shape[1]):
        out[:, axis] = np.bincount(i, values[:, axis], n) - np.bincount(
            j, values[:, axis], n
        )
    return out


def gather(i, j, directions, n):
    """Sum the neighbours' headings for every boid."""
    out = np.empty_like(directions)
    for axis in range(directions.shape[1]):
        column = directions[:, axis]
        out[:, axis] = np.bincount(i, column[j], n) + np.bincount(j, column[i], n)
    return out


class Flock(Model):
    """The torus, its boids and the vectorised step."""

    def __init__(
        self, n, side, vision, speed, separation, cohere, separate, match, rng
    ):
        super().__init__(rng=rng)
        self.vision, self.speed, self.separation = vision, speed, separation
        self.cohere, self.separate, self.match = cohere, separate, match
        self.space = ContinuousSpace(
            [[0, side], [0, side]], torus=True, random=self.random, n_agents=n
        )
        start = np.random.default_rng(rng)
        positions = start.random((n, 2)) * side
        angles = start.random(n) * 2 * np.pi
        self.directions = np.column_stack([np.cos(angles), np.sin(angles)])
        for i in range(n):
            Boid(self.space, self).position = positions[i]
        self.neighbor_counts = np.zeros(n)
        self.polarisation = []

    def step(self):
        space, directions = self.space, self.directions
        n = directions.shape[0]
        i, j = pairs_within(space, self.vision)
        delta = difference_vectors(space, i, j)
        close = (delta**2).sum(axis=1) < self.separation**2
        count = np.bincount(i, minlength=n) + np.bincount(j, minlength=n)
        steer = scatter(i, j, delta, n) * self.cohere
        steer -= scatter(i[close], j[close], delta[close], n) * self.separate
        steer += gather(i, j, directions, n) * self.match
        new = directions + steer / np.maximum(count, 1)[:, None]
        new /= np.linalg.norm(new, axis=1, keepdims=True)
        directions[:] = new
        move_all(space, space.agent_positions + directions * self.speed)
        self.neighbor_counts = count
        self.polarisation.append(float(np.linalg.norm(directions.mean(axis=0))))


def build(seed, n, side, vision, speed, separation, cohere, separate, match):
    """Build the model."""
    return Flock(n, side, vision, speed, separation, cohere, separate, match, seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    model.run_for(steps)
    return {
        "population": int(model.directions.shape[0]),
        "stats": {
            "final_polarisation": model.polarisation[-1],
            "mean_polarisation": sum(model.polarisation) / len(model.polarisation),
            "mean_neighbors": float(model.neighbor_counts.mean()),
        },
    }
