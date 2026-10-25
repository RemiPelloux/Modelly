"""Flocking (boids) on a torus, simultaneous update, written for Mesa 3.5.

Same model as ``mesa_model.py``. Every boid steers towards the centre of its
neighbours within ``vision`` (cohere), away from those closer than
``separation`` (separate) and along their headings (match), all read from the
start-of-step state, then moves ``speed`` along its new unit heading. The
space is ``mesa.space.ContinuousSpace``, which Mesa 3.5 still provides without
deprecation: on this workload it is about 1.6 times faster than the experimental
``mesa.experimental.continuous_space`` that Mesa's boid_flockers example uses
(same runs, bit for bit), so the faster one is the fairer baseline.
"""

from __future__ import annotations

import mesa
import numpy as np
from mesa.space import ContinuousSpace


class Boid(mesa.Agent):
    """A boid with a unit heading; ``compute`` then ``advance`` keep the update simultaneous."""

    def __init__(self, model, direction):
        super().__init__(model)
        self.direction = direction
        self.new_direction = direction
        self.neighbor_count = 0

    def compute(self):
        model = self.model
        neighbors = model.space.get_neighbors(
            self.pos, model.vision, include_center=False
        )
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
    """The torus and its boids."""

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
        for i in range(n):
            boid = Boid(self, np.array([np.cos(angles[i]), np.sin(angles[i])]))
            self.space.place_agent(boid, tuple(positions[i]))
        self.polarisation = []

    def step(self):
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
