"""Predator-prey with grass regrowth, written for Modelly with columnar agents.

Same model as ``mesa_model.py``. Each animal's cell is a column of cell rows,
so the whole step is array work: movement by ``random_neighbor``, energy by a
column subtraction, grazing by a random permutation (one sheep per grown
cell), predation by ``claim`` (every wolf takes one distinct sheep of its cell
if any is left, with the law of the shuffled sequential rule), deaths by
``remove_where``, births by one ``create_agents`` call per species.
"""

from __future__ import annotations

import numpy as np

from modelly import Agent, Column, Model
from modelly.discrete_space import (
    NO_MATCH,
    CellIndex,
    Occupancy,
    OrthogonalMooreGrid,
    claim,
)


class Animal(Agent):
    """Energy and cell row live in the species' column table."""

    energy = Column(float, default=0.0)
    row = Column(np.intp, default=-1)

    def __init__(self, model, row, energy):
        super().__init__(model)
        self.row = row
        self.energy = energy


class Sheep(Animal):
    """Grazes."""


class Wolf(Animal):
    """Hunts sheep."""


class PredatorPrey(Model):
    """The grid topology, the grass layer and the animals."""

    def __init__(
        self,
        side,
        sheep,
        wolves,
        sheep_reproduce,
        wolf_reproduce,
        sheep_gain,
        wolf_gain,
        regrowth,
        rng,
    ):
        super().__init__(rng=rng)
        self.p_sheep, self.p_wolf = sheep_reproduce, wolf_reproduce
        self.sheep_gain, self.wolf_gain, self.regrowth = sheep_gain, wolf_gain, regrowth
        self.grid = OrthogonalMooreGrid((side, side), torus=True, random=self.random)
        self.index = CellIndex(self.grid)
        self.grass = self.grid.create_property_layer("grass", 0, dtype=np.int64)
        self.grass[:] = self.rng.integers(0, regrowth + 1, size=(side, side))
        self.grass_flat = self.grass.reshape(-1)
        self._populate(Sheep, sheep, sheep_gain)
        self._populate(Wolf, wolves, wolf_gain)
        self.history = []

    def _populate(self, species, count, gain):
        species.create_agents(
            self,
            count,
            row=self.rng.integers(0, len(self.index), count),
            energy=self.rng.random(count) * 2 * gain,
        )

    def graze(self, table):
        """One uniformly random sheep per grown cell eats the grass."""
        rows = table.row
        candidates = np.flatnonzero(self.grass_flat[rows] == 0)
        if candidates.shape[0] == 0:
            return
        order = self.rng.permutation(candidates)
        cells, first = np.unique(rows[order], return_index=True)
        table.energy[order[first]] += self.sheep_gain
        self.grass_flat[cells] = self.regrowth

    def hunt(self, sheep, wolves):
        """Every wolf eats one distinct sheep of its cell, if one is left."""
        prey = claim(Occupancy(sheep.row, len(self.index)), wolves.row, self.rng)
        fed = prey != NO_MATCH
        wolves.energy[fed] += self.wolf_gain
        eaten = np.zeros(len(sheep), dtype=bool)
        eaten[prey[fed]] = True
        sheep.remove_where(eaten)

    def reproduce(self, species, table, p):
        """Each animal spawns a copy in its cell with half its energy, with probability p."""
        parents = table.draw(p)
        count = int(parents.sum())
        if count:
            table.energy[parents] /= 2
            species.create_agents(
                self, count, row=table.row[parents], energy=table.energy[parents]
            )

    def step(self):
        sheep, wolves = self.columns[Sheep], self.columns[Wolf]
        for table in (sheep, wolves):
            table.row = self.index.random_neighbor(table.row, self.rng)
            table.energy -= 1
        self.graze(sheep)
        self.hunt(sheep, wolves)
        sheep.remove_where(sheep.energy < 0)
        wolves.remove_where(wolves.energy < 0)
        self.reproduce(Sheep, sheep, self.p_sheep)
        self.reproduce(Wolf, wolves, self.p_wolf)
        np.maximum(self.grass - 1, 0, out=self.grass)
        self.history.append((len(sheep), len(wolves), float((self.grass == 0).mean())))


def build(
    seed,
    side,
    sheep,
    wolves,
    sheep_reproduce,
    wolf_reproduce,
    sheep_gain,
    wolf_gain,
    regrowth,
):
    """Build the model."""
    return PredatorPrey(
        side,
        sheep,
        wolves,
        sheep_reproduce,
        wolf_reproduce,
        sheep_gain,
        wolf_gain,
        regrowth,
        seed,
    )


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    model.run_for(steps)
    return summarise(model.history)


def summarise(history):
    """Final and mean counts over the run."""
    sheep = [h[0] for h in history]
    wolves = [h[1] for h in history]
    grass = [h[2] for h in history]
    return {
        "population": sheep[-1] + wolves[-1],
        "stats": {
            "final_sheep": sheep[-1],
            "final_wolves": wolves[-1],
            "mean_sheep": sum(sheep) / len(sheep),
            "mean_wolves": sum(wolves) / len(wolves),
            "mean_grass": sum(grass) / len(grass),
        },
    }
