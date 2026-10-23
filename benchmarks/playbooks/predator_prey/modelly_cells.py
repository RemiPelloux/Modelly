"""Predator-prey with grass regrowth, written for Modelly with agents held in cell lists.

Same model as ``mesa_model.py``, with the same data structure as Mesa: every
cell keeps the list of its agents. Movement and wolf predation stay per agent;
energy loss, sheep grazing (one random sheep per grown cell, chosen through a
random permutation), deaths and the reproduction draws are column operations.
"""

from __future__ import annotations

import numpy as np

from modelly import Column, Model
from modelly.discrete_space import CellAgent, CellIndex, OrthogonalMooreGrid


class Animal(CellAgent):
    """Energy and cell row live in the species' column table."""

    energy = Column(float, default=0.0)
    row = Column(np.intp, default=-1)

    def __init__(self, model, cell, energy):
        super().__init__(model)
        self.cell = cell
        self.row = cell.index
        self.energy = energy

    def move(self):
        cell = self.cell.neighborhood.select_random_cell()
        self.cell = cell
        self.row = cell.index

    def spawn(self):
        self.energy /= 2
        type(self)(self.model, self.cell, self.energy)


class Sheep(Animal):
    """Grazes; the grazing phase is vectorised at model level."""


class Wolf(Animal):
    """Eats one sheep of its cell."""

    def eat(self):
        sheep = [a for a in self.cell.agents if isinstance(a, Sheep)]
        if sheep:
            self.random.choice(sheep).remove()
            self.energy += self.model.wolf_gain


class PredatorPrey(Model):
    """The grid, the grass layer and the animals."""

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
            cell=self.random.choices(self.index.cells, k=count),
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
        winners = order[first]
        table.energy[winners] += self.sheep_gain
        self.grass_flat[cells] = self.regrowth

    def step(self):
        sheep, wolves = self.columns[Sheep], self.columns[Wolf]
        self.agents_by_type[Sheep].shuffle_do("move")
        self.agents_by_type[Wolf].shuffle_do("move")
        sheep.energy -= 1
        wolves.energy -= 1
        self.graze(sheep)
        self.agents_by_type[Wolf].shuffle_do("eat")
        sheep.remove_where(sheep.energy < 0)
        wolves.remove_where(wolves.energy < 0)
        sheep.do_where(sheep.draw(self.p_sheep), "spawn")
        wolves.do_where(wolves.draw(self.p_wolf), "spawn")
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
