"""Predator-prey with grass regrowth, written for Mesa 2.3.

Every step, in this order: all animals move to a random Moore neighbour cell
and lose one energy; in each cell with grown grass one sheep (the first in the
shuffled order) eats it; each wolf eats one random sheep of its cell, if any;
animals with negative energy die; each survivor reproduces with its species'
probability, giving half its energy to a copy in the same cell; grass regrows
one day on every cell (a numpy operation on the property layer).
"""

from __future__ import annotations

import mesa
import numpy as np
from mesa.space import MultiGrid, PropertyLayer


class Animal(mesa.Agent):
    """Moves, eats, dies, reproduces."""

    def __init__(self, unique_id, model, energy):
        super().__init__(unique_id, model)
        self.energy = energy

    def move(self):
        grid = self.model.grid
        cells = grid.get_neighborhood(self.pos, moore=True)
        grid.move_agent(self, self.random.choice(cells))
        self.energy -= 1

    def die(self):
        self.model.grid.remove_agent(self)
        self.remove()

    def spawn(self):
        self.energy /= 2
        child = type(self)(self.model.next_id(), self.model, self.energy)
        self.model.grid.place_agent(child, self.pos)


class Sheep(Animal):
    """Eats grown grass."""

    def eat(self):
        grass = self.model.grass.data
        if grass[self.pos] == 0:
            grass[self.pos] = self.model.regrowth
            self.energy += self.model.sheep_gain


class Wolf(Animal):
    """Eats one sheep of its cell."""

    def eat(self):
        cellmates = self.model.grid.get_cell_list_contents([self.pos])
        sheep = [a for a in cellmates if isinstance(a, Sheep)]
        if sheep:
            self.random.choice(sheep).die()
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
        seed,
    ):
        super().__init__(seed=seed)
        self.p_sheep, self.p_wolf = sheep_reproduce, wolf_reproduce
        self.sheep_gain, self.wolf_gain, self.regrowth = sheep_gain, wolf_gain, regrowth
        self.grid = MultiGrid(side, side, torus=True)
        self.grass = PropertyLayer("grass", side, side, 0, dtype=np.int64)
        rng = np.random.default_rng(seed)
        self.grass.data[:] = rng.integers(0, regrowth + 1, size=(side, side))
        self._populate(Sheep, sheep, sheep_gain, side)
        self._populate(Wolf, wolves, wolf_gain, side)
        self.history = []

    def _populate(self, species, count, gain, side):
        for _ in range(count):
            animal = species(self.next_id(), self, self.random.uniform(0, 2 * gain))
            pos = (self.random.randrange(side), self.random.randrange(side))
            self.grid.place_agent(animal, pos)

    def _shuffled(self, species):
        animals = list(self.get_agents_of_type(species))
        self.random.shuffle(animals)
        return animals

    def step(self):
        sheep, wolves = self._shuffled(Sheep), self._shuffled(Wolf)
        for animal in sheep + wolves:
            animal.move()
        for animal in sheep:
            animal.eat()
        for animal in wolves:
            animal.eat()
        alive = [a for a in sheep + wolves if a.pos is not None]
        for animal in alive:
            if animal.energy < 0:
                animal.die()
        for animal in alive:
            p = self.p_sheep if isinstance(animal, Sheep) else self.p_wolf
            if animal.pos is not None and self.random.random() < p:
                animal.spawn()
        grass = self.grass.data
        np.maximum(grass - 1, 0, out=grass)
        self.history.append(
            (
                len(self.get_agents_of_type(Sheep)),
                len(self.get_agents_of_type(Wolf)),
                float((grass == 0).mean()),
            )
        )


# Mesa 2.3 seeds ``model.random`` in ``Model.__new__`` from the keyword ``seed``;
# a positional seed leaves the model unseeded.
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
        seed=seed,
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
