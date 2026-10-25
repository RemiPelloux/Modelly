"""Flocking (boids) on a torus, simultaneous update, written for Mesa 3.5.

Same model as ``mesa_model.py``. Every boid steers towards the centre of its
neighbours within ``vision`` (cohere), away from those closer than
``separation`` (separate) and along their headings (match), all read from the
start-of-step state, then moves ``speed`` along its new unit heading. The
space is ``mesa.experimental.continuous_space.ContinuousSpace``, as in Mesa's
own boid_flockers example; it answers each neighbour query with a scan of every
position held in its numpy array.
"""

from __future__ import annotations

import numpy as np
from mesa import Model
from mesa.experimental.continuous_space import ContinuousSpace, ContinuousSpaceAgent


class Boid(ContinuousSpaceAgent):
    """A boid with a unit heading; ``compute`` then ``advance`` keep the update simultaneous."""

    def __init__(self, model, space, position, direction):
        super().__init__(space, model)
        self.position = position
        self.direction = direction
        self.new_direction = direction
        self.neighbor_count = 0

    def compute(self):
        model = self.model
        neighbors, distances = self.get_neighbors_in_radius(radius=model.vision)
        self.neighbor_count = len(neighbors)
        if not neighbors:
            self.new_direction = self.direction
            return
        delta = self.space.calculate_difference_vector(self.position, agents=neighbors)
        cohere = delta.sum(axis=0) * model.cohere
        separate = -delta[distances < model.separation].sum(axis=0) * model.separate
        match = np.asarray([n.direction for n in neighbors]).sum(axis=0) * model.match
        direction = self.direction + (cohere + separate + match) / len(neighbors)
        self.new_direction = direction / np.linalg.norm(direction)

    def advance(self):
        self.direction = self.new_direction
        self.position = self.position + self.direction * self.model.speed


class Flock(Model):
    """The torus and its boids."""

    def __init__(
        self, n, side, vision, speed, separation, cohere, separate, match, rng
    ):
        super().__init__(rng=rng)
        self.vision, self.speed, self.separation = vision, speed, separation
        self.cohere, self.separate, self.match = cohere, separate, match
        self.space = ContinuousSpace(
            [[0, side], [0, side]], torus=True, random=self.random, n_agents=n
        )
        # ``Model(rng=seed)`` makes ``self.rng`` ``np.random.default_rng(seed)``,
        # the stream the reference draws its initial state from.
        positions = self.rng.random((n, 2)) * side
        angles = self.rng.random(n) * 2 * np.pi
        directions = np.column_stack([np.cos(angles), np.sin(angles)])
        Boid.create_agents(self, n, self.space, positions, directions)
        self.polarisation = []

    def step(self):
        self.agents.do("compute")
        self.agents.do("advance")
        mean = np.mean([a.direction for a in self.agents], axis=0)
        self.polarisation.append(float(np.linalg.norm(mean)))


def build(seed, n, side, vision, speed, separation, cohere, separate, match):
    """Build the model."""
    return Flock(n, side, vision, speed, separation, cohere, separate, match, rng=seed)


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
