"""Flocking (boids) on a torus for Mesa 3.5, with neighbours found by a KD-tree.

Same model and same Mesa code as ``mesa3_model.py``, with one change: instead of
``ContinuousSpace.get_neighbors``, which tests every boid's distance to every other,
each step builds one periodic ``scipy.spatial.cKDTree`` over the start-of-step
positions and every boid asks it for the neighbours within ``vision``. The agents,
their per-agent steering and the space stay Mesa's. It is the baseline a Mesa
modeller gets by adding the search Modelly's column form uses, so that the gap to
Modelly separates the algorithm from the per-agent Python loop.
"""

from __future__ import annotations

import mesa
import numpy as np
from mesa.space import ContinuousSpace
from scipy.spatial import cKDTree


class Boid(mesa.Agent):
    """A boid with a unit heading; ``compute`` then ``advance`` keep the update simultaneous."""

    def __init__(self, model, direction):
        super().__init__(model)
        self.direction = direction
        self.new_direction = direction
        self.neighbor_count = 0

    def compute(self):
        model = self.model
        neighbors = [
            model.boids[j] for j in model.neighbors[self.index] if j != self.index
        ]
        self.neighbor_count = len(neighbors)
        if not neighbors:
            self.new_direction = self.direction
            return
        size = model.size
        delta = np.array([n.pos for n in neighbors]) - self.pos
        delta = np.mod(delta + size / 2, size) - size / 2
        close = (delta**2).sum(axis=1) < model.separation**2
        cohere = delta.sum(axis=0) * model.cohere
        separate = -delta[close].sum(axis=0) * model.separate
        match = np.array([n.direction for n in neighbors]).sum(axis=0) * model.match
        direction = self.direction + (cohere + separate + match) / len(neighbors)
        self.new_direction = direction / np.linalg.norm(direction)

    def advance(self):
        self.direction = self.new_direction
        self.model.space.move_agent(
            self, tuple(self.pos + self.direction * self.model.speed)
        )


class Flock(mesa.Model):
    """The torus, its boids, and the step's KD-tree of their positions."""

    def __init__(
        self, n, side, vision, speed, separation, cohere, separate, match, seed
    ):
        super().__init__(rng=seed)
        self.vision, self.speed, self.separation = vision, speed, separation
        self.cohere, self.separate, self.match = cohere, separate, match
        self.size = np.array([side, side])
        self.space = ContinuousSpace(side, side, torus=True)
        rng = np.random.default_rng(seed)
        positions = rng.random((n, 2)) * side
        angles = rng.random(n) * 2 * np.pi
        self.boids = []
        for i in range(n):
            boid = Boid(self, np.array([np.cos(angles[i]), np.sin(angles[i])]))
            boid.index = i
            self.space.place_agent(boid, tuple(positions[i]))
            self.boids.append(boid)
        self.neighbors = []
        self.polarisation = []

    def find_neighbors(self):
        """Every boid's neighbours within ``vision``, from one periodic KD-tree."""
        # The tree wants coordinates in [0, side); the space keeps them there on a torus.
        points = np.mod([b.pos for b in self.boids], self.size)
        tree = cKDTree(points, boxsize=self.size)
        self.neighbors = [
            sorted(js) for js in tree.query_ball_point(points, self.vision)
        ]

    def step(self):
        self.find_neighbors()
        agents = self.agents
        agents.do("compute")
        agents.do("advance")
        mean = np.mean([a.direction for a in agents], axis=0)
        self.polarisation.append(float(np.linalg.norm(mean)))


def build(seed, n, side, vision, speed, separation, cohere, separate, match):
    """Build the model."""
    return Flock(n, side, vision, speed, separation, cohere, separate, match, seed=seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    for _ in range(steps):
        model.step()
    counts = [a.neighbor_count for a in model.agents]
    return {
        "population": len(counts),
        "stats": {
            "final_polarisation": model.polarisation[-1],
            "mean_polarisation": sum(model.polarisation) / len(model.polarisation),
            "mean_neighbors": sum(counts) / len(counts),
        },
    }
