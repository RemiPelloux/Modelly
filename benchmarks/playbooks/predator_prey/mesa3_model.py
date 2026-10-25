"""Predator-prey with grass regrowth, written for Mesa 3.5.

Every step, in this order: all animals move to a random Moore neighbour cell
and lose one energy; in each cell with grown grass one sheep (the first in the
shuffled order) eats it; each wolf eats one random sheep of its cell, if any;
animals with negative energy die; each survivor reproduces with its species'
probability, giving half its energy to a copy in the same cell; grass regrows
one day on every cell (a numpy operation on the grid's property layer, as in
Mesa's Sugarscape example). Animals are ``CellAgent`` objects on an
``OrthogonalMooreGrid``; each phase is one ``shuffle_do`` or ``do`` over the
model's agent sets, which skip agents removed earlier in the phase and do not
reach agents born during it.
"""

from __future__ import annotations

import mesa
import numpy as np
from mesa.discrete_space import CellAgent, OrthogonalMooreGrid


class Animal(CellAgent):
    """Moves, eats, dies, reproduces."""

    def __init__(self, model, energy, cell):
        super().__init__(model)
        self.energy = energy
        self.cell = cell

    def move(self):
        self.cell = self.cell.neighborhood.select_random_cell()
        self.energy -= 1

    def starve(self):
        if self.energy < 0:
            self.remove()

    def reproduce(self):
        if self.random.random() < self.p_reproduce:
            self.energy /= 2
            type(self)(self.model, self.energy, self.cell)


class Sheep(Animal):
    """Eats grown grass."""

    @property
    def p_reproduce(self):
        return self.model.p_sheep

    def eat(self):
        cell = self.cell
        if cell.grass == 0:
            cell.grass = self.model.regrowth
            self.energy += self.model.sheep_gain


class Wolf(Animal):
    """Eats one sheep of its cell."""

    @property
    def p_reproduce(self):
        return self.model.p_wolf

    def eat(self):
        sheep = [a for a in self.cell.agents if isinstance(a, Sheep)]
        if sheep:
            self.random.choice(sheep).remove()
            self.energy += self.model.wolf_gain


class PredatorPrey(mesa.Model):
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
        grass = self.grid.create_property_layer("grass", default_value=0, dtype=int)
        grass.data = self.rng.integers(0, regrowth + 1, size=(side, side))
        self._populate(Sheep, sheep, sheep_gain)
        self._populate(Wolf, wolves, wolf_gain)
        self.history = []

    def _populate(self, species, count, gain):
        species.create_agents(
            self,
            count,
            energy=[self.random.uniform(0, 2 * gain) for _ in range(count)],
            cell=self.random.choices(self.grid.all_cells.cells, k=count),
        )

    def step(self):
        self.agents.shuffle_do("move")
        self.agents_by_type[Sheep].shuffle_do("eat")
        self.agents_by_type[Wolf].shuffle_do("eat")
        self.agents.do("starve")
        self.agents.shuffle_do("reproduce")
        grass = self.grid.grass
        grass.data = np.maximum(grass.data - 1, 0)
        self.history.append(
            (
                len(self.agents_by_type[Sheep]),
                len(self.agents_by_type[Wolf]),
                float((grass.data == 0).mean()),
            )
        )


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
        rng=seed,
    )


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    for _ in range(steps):
        model.step()
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
