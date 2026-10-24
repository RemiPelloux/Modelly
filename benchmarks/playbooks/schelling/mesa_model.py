"""Schelling segregation on a torus grid, written for Mesa 2.3.

At most one resident per cell (``SingleGrid``). Every step: each resident
counts the residents of its own kind among its eight Moore neighbours, all from
the configuration at the start of the step, and is happy when the count reaches
``homophily``; the unhappy residents then move one at a time, in a random
order, each to a uniformly random empty cell (``SingleGrid.move_to_empty``).
The initial configuration is drawn with numpy from the seed.
"""

from __future__ import annotations

import mesa
import numpy as np
from mesa.space import SingleGrid


class Resident(mesa.Agent):
    """One resident of kind 0 (majority) or 1 (minority)."""

    def __init__(self, unique_id, model, kind):
        super().__init__(unique_id, model)
        self.kind = kind
        self.happy = False

    def neighbours(self):
        return list(self.model.grid.iter_neighbors(self.pos, moore=True))

    def assess(self):
        similar = sum(1 for other in self.neighbours() if other.kind == self.kind)
        self.happy = similar >= self.model.homophily

    def relocate(self):
        self.model.grid.move_to_empty(self)


class Schelling(mesa.Model):
    """The grid, the residents and the two-phase step."""

    def __init__(self, side, density, minority, homophily, seed):
        super().__init__(seed=seed)
        self.homophily = homophily
        self.grid = SingleGrid(side, side, torus=True)
        rng = np.random.default_rng(seed)
        occupied = np.flatnonzero(rng.random(side * side) < density)
        kinds = (rng.random(occupied.shape[0]) < minority).astype(int)
        for uid, (cell, kind) in enumerate(zip(occupied.tolist(), kinds.tolist())):
            self.grid.place_agent(Resident(uid, self, kind), divmod(cell, side))
        self.history = []

    def step(self):
        agents = self.agents
        agents.do("assess")
        unhappy = agents.select(lambda a: not a.happy)
        unhappy.shuffle(inplace=True).do("relocate")
        self.history.append((1 - len(unhappy) / len(agents), len(unhappy)))


# Mesa 2.3 seeds ``model.random`` in ``Model.__new__`` from the keyword ``seed``;
# a positional seed leaves the model unseeded.
def build(seed, side, density, minority, homophily):
    """Build the model."""
    return Schelling(side, density, minority, homophily, seed=seed)


def segregation(model):
    """Mean share of same-kind neighbours, over residents with any neighbour."""
    shares = []
    for agent in model.agents:
        neighbours = agent.neighbours()
        if neighbours:
            same = sum(1 for other in neighbours if other.kind == agent.kind)
            shares.append(same / len(neighbours))
    return sum(shares) / len(shares)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    for _ in range(steps):
        model.step()
    happy = [h[0] for h in model.history]
    moves = [h[1] for h in model.history]
    return {
        "population": len(model.agents),
        "stats": {
            "final_happy": happy[-1],
            "mean_happy": sum(happy) / len(happy),
            "total_moves": sum(moves),
            "segregation": segregation(model),
        },
    }
