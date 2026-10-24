"""Sugarscape with constant growback, written for Mesa 2.3.

A non-toroidal grid with a sugar ``PropertyLayer`` (two hills) and at most one
forager per cell (``SingleGrid``). Every step the foragers act one at a time in
a random order: each looks at the cells within its vision (von Neumann
distance), and moves to the free one with the most sugar if it holds more than
its own cell, the nearest such cell, then a random one, breaking ties; it eats
all the sugar of its cell, burns its metabolism and starves when its store
falls to zero. Then every cell grows back ``growback`` sugar up to its
capacity (a numpy operation on the layer). The landscape and the foragers are
drawn with numpy from the seed.
"""

from __future__ import annotations

import mesa
import numpy as np
from mesa.space import PropertyLayer, SingleGrid


class Forager(mesa.Agent):
    """Sees, moves, eats, starves."""

    def __init__(self, unique_id, model, vision, metabolism, wealth):
        super().__init__(unique_id, model)
        self.vision = vision
        self.metabolism = metabolism
        self.wealth = wealth

    def move(self):
        grid, sugar = self.model.grid, self.model.sugar.data
        mask = grid.get_neighborhood_mask(
            self.pos, moore=False, include_center=False, radius=self.vision
        )
        best = grid.select_cells(
            extreme_values={"sugar": "highest"}, masks=mask, only_empty=True
        )
        if not best or sugar[best[0]] <= sugar[self.pos]:
            return
        x, y = self.pos
        distance = [abs(int(bx) - x) + abs(int(by) - y) for bx, by in best]
        nearest = [cell for cell, d in zip(best, distance) if d == min(distance)]
        bx, by = self.random.choice(nearest)
        grid.move_agent(self, (int(bx), int(by)))

    def eat(self):
        sugar = self.model.sugar.data
        self.wealth += int(sugar[self.pos]) - self.metabolism
        sugar[self.pos] = 0
        if self.wealth <= 0:
            self.model.grid.remove_agent(self)
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

    def __init__(self, side, n, params, seed):
        super().__init__(seed=seed)
        self.growback = params["growback"]
        self.grid = SingleGrid(side, side, torus=False)
        self.capacity = landscape(
            side, params["max_sugar"], params["peaks"], params["spread"]
        )
        self.sugar = PropertyLayer("sugar", side, side, 0, dtype=np.int64)
        self.sugar.data[:] = self.capacity
        self.grid.add_property_layer(self.sugar)
        self._populate(side, n, params, np.random.default_rng(seed))
        self.history = []

    def _populate(self, side, n, params, rng):
        cells = rng.choice(side * side, n, replace=False).tolist()
        traits = [
            rng.integers(lo, hi + 1, n).tolist()
            for lo, hi in (params[k] for k in ("vision", "metabolism", "initial_sugar"))
        ]
        for uid, (cell, *trait) in enumerate(zip(cells, *traits)):
            self.grid.place_agent(Forager(uid, self, *trait), divmod(cell, side))

    def step(self):
        self.agents.shuffle(inplace=True).do("step")
        sugar = self.sugar.data
        np.minimum(sugar + self.growback, self.capacity, out=sugar)
        self.history.append(len(self.agents))


# Mesa 2.3 seeds ``model.random`` in ``Model.__new__`` from the keyword ``seed``;
# a positional seed leaves the model unseeded.
def build(seed, side, n, **params):
    """Build the model."""
    return Sugarscape(side, n, params, seed=seed)


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
            "sugar_left": int(model.sugar.data.sum()),
        },
    }
