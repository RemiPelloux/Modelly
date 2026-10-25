"""Sugarscape with constant growback, written for Mesa 3.5.

A non-toroidal ``OrthogonalVonNeumannGrid`` with a sugar ``PropertyLayer`` (two
hills) and at most one forager per cell (capacity one). Every step the
foragers act one at a time in a random order (``shuffle_do``): each looks at
the cells within its vision (``cell.get_neighborhood(radius=vision)``, von
Neumann distance), and moves to the empty one with the most sugar if it holds
more than its own cell, the nearest such cell, then a random one, breaking
ties; it eats all the sugar of its cell, burns its metabolism and starves when
its store falls to zero. Then every cell grows back ``growback`` sugar up to
its capacity (a numpy operation on the layer, as in Mesa's Sugarscape
example). The foragers start on distinct random cells with traits drawn from
the model's random generators.
"""

from __future__ import annotations

import mesa
import numpy as np
from mesa.discrete_space import CellAgent, OrthogonalVonNeumannGrid, PropertyLayer

TRAITS = ("vision", "metabolism", "initial_sugar")


class Forager(CellAgent):
    """Sees, moves, eats, starves."""

    def __init__(self, model, cell, vision, metabolism, initial_sugar):
        super().__init__(model)
        self.cell = cell
        self.vision = vision
        self.metabolism = metabolism
        self.wealth = initial_sugar

    def best_cells(self):
        """The nearest free cells in sight holding the most sugar, if more than here.

        One pass over the cached neighbourhood, the same loop as the other variants.
        """
        here = self.cell
        best, most, nearest = [], here.sugar, 0
        x, y = here.coordinate
        for cell in here.get_neighborhood(radius=self.vision):
            if not cell.is_empty or cell.sugar < most:
                continue
            distance = abs(cell.coordinate[0] - x) + abs(cell.coordinate[1] - y)
            if cell.sugar > most or distance < nearest:
                best, most, nearest = [cell], cell.sugar, distance
            elif distance == nearest:
                best.append(cell)
        return best

    def move(self):
        best = self.best_cells()
        if best:
            self.cell = self.random.choice(best)

    def eat(self):
        cell = self.cell
        self.wealth += int(cell.sugar) - self.metabolism
        cell.sugar = 0
        if self.wealth <= 0:
            self.remove()

    def step(self):
        self.move()
        self.eat()


def landscape(side, max_sugar, peaks, spread):
    """Sugar capacity of every cell: Gaussian hills rounded to whole units."""
    x = (np.arange(side) + 0.5) / side
    xx, yy = np.meshgrid(x, x, indexing="ij")
    hills = [
        np.exp(-((xx - px) ** 2 + (yy - py) ** 2) / (2 * spread**2)) for px, py in peaks
    ]
    return np.rint(max_sugar * np.maximum.reduce(hills)).astype(np.int64)


class Sugarscape(mesa.Model):
    """The grid, the sugar layer and the foragers."""

    def __init__(self, side, n, params, rng):
        super().__init__(rng=rng)
        self.growback = params["growback"]
        self.grid = OrthogonalVonNeumannGrid(
            (side, side), torus=False, capacity=1, random=self.random
        )
        self.capacity = landscape(
            side, params["max_sugar"], params["peaks"], params["spread"]
        )
        self.grid.add_property_layer(PropertyLayer.from_data("sugar", self.capacity))
        self._populate(n, params)
        self.history = []

    def _populate(self, n, params):
        cells = self.random.sample(self.grid.all_cells.cells, k=n)
        traits = {
            name: self.rng.integers(*params[name], n, endpoint=True).tolist()
            for name in TRAITS
        }
        Forager.create_agents(self, n, cells, **traits)

    def step(self):
        self.agents.shuffle_do("step")
        sugar = self.grid.sugar
        sugar.data = np.minimum(sugar.data + self.growback, self.capacity)
        self.history.append(len(self.agents))


def build(seed, side, n, **params):
    """Build the model."""
    return Sugarscape(side, n, params, rng=seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    for _ in range(steps):
        model.step()
    agents = list(model.agents)
    history = model.history
    return {
        "population": len(agents),
        "stats": {
            "final_population": history[-1],
            "mean_population": sum(history) / len(history),
            "mean_vision": sum(a.vision for a in agents) / len(agents),
            "mean_metabolism": sum(a.metabolism for a in agents) / len(agents),
            "mean_wealth": sum(a.wealth for a in agents) / len(agents),
            "sugar_left": int(model.grid.sugar.data.sum()),
        },
    }
