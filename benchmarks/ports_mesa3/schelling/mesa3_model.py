"""Schelling segregation on a torus grid, ported from Mesa 3.5 to Modelly by the codemod alone (see ../README.md).

At most one resident per cell (an ``OrthogonalMooreGrid`` with capacity one).
Every step: each resident counts the residents of its own kind among its eight
Moore neighbours (``cell.neighborhood``), all from the configuration at the
start of the step, and is happy when the count reaches ``homophily``; the
unhappy residents then move one at a time, in a random order
(``shuffle_do``), each to a uniformly random empty cell
(``select_random_empty_cell``). Each cell is occupied with probability
``density`` and each resident is of the minority kind with probability
``minority``, drawn from the model's own random generator.
"""

from __future__ import annotations

import modelly
from modelly.space import CellAgent, OrthogonalMooreGrid

MAJORITY, MINORITY = 0, 1


class Resident(CellAgent):
    """One resident of kind 0 (majority) or 1 (minority)."""

    def __init__(self, model, cell, kind):
        super().__init__(model)
        self.cell = cell
        self.kind = kind
        self.happy = False

    def neighbours(self):
        return list(self.cell.neighborhood.agents)

    def assess(self):
        similar = sum(1 for other in self.neighbours() if other.kind == self.kind)
        self.happy = similar >= self.model.homophily

    def relocate(self):
        self.cell = self.model.grid.select_random_empty_cell()


class Schelling(modelly.Model):
    """The grid, the residents and the two-phase step."""

    def __init__(self, side, density, minority, homophily, rng):
        super().__init__(rng=rng)
        self.homophily = homophily
        self.grid = OrthogonalMooreGrid(
            (side, side), torus=True, capacity=1, random=self.random
        )
        for cell in self.grid.all_cells:
            if self.random.random() < density:
                kind = MINORITY if self.random.random() < minority else MAJORITY
                Resident(self, cell, kind)
        self.history = []

    def step(self):
        agents = self.agents
        agents.do("assess")
        unhappy = agents.select(lambda a: not a.happy)
        unhappy.shuffle_do("relocate")
        self.history.append((1 - len(unhappy) / len(agents), len(unhappy)))


def build(seed, side, density, minority, homophily):
    """Build the model."""
    return Schelling(side, density, minority, homophily, rng=seed)


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
