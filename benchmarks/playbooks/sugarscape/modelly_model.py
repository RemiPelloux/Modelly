"""Sugarscape with constant growback, written for Modelly with columnar agents.

Same model as ``mesa_model.py``. Each forager's cell is a column of cell rows
and the sugar a property layer. The moves stay sequential, since a forager's
choice depends on the cells freed and taken before its turn, but all the
looking is one array pass (docs/vectorised_phases.md, §9): every forager's
visible cells (one table of von Neumann offsets), their sugar, and its ranking
of the cells richer than its own, by sugar, then distance, then a random key.
The loop only walks each ranked list to its first free cell. Eating, burning
and starving are column operations after the loop, which is exact: a cell a
forager takes stays taken, and one it frees by starving holds no sugar, so it
cannot attract a later forager.
"""

from __future__ import annotations

import numpy as np

from modelly import Agent, Column, Model
from modelly.space import CellIndex, OrthogonalVonNeumannGrid

# column -> registry range it is drawn from, in the order the Mesa version draws them
TRAITS = {"vision": "vision", "metabolism": "metabolism", "wealth": "initial_sugar"}


class Forager(Agent):
    """Traits, store and cell row live in the model's column table."""

    vision = Column(np.int64, default=1)
    metabolism = Column(np.int64, default=1)
    wealth = Column(np.int64, default=0)
    row = Column(np.intp, default=-1)

    def __init__(self, model, row, vision, metabolism, wealth):
        super().__init__(model)
        self.row = row
        self.vision = vision
        self.metabolism = metabolism
        self.wealth = wealth


def landscape(side, max_sugar, peaks, spread):
    """Sugar capacity of every cell: Gaussian hills rounded to whole units."""
    x = (np.arange(side) + 0.5) / side
    xx, yy = np.meshgrid(x, x, indexing="ij")
    hills = [
        np.exp(-((xx - px) ** 2 + (yy - py) ** 2) / (2 * spread**2)) for px, py in peaks
    ]
    return np.rint(max_sugar * np.maximum.reduce(hills)).astype(np.int64)


def sight(side, radius):
    """For every cell, the rows within von Neumann distance 1 to ``radius``.

    Returns the target rows (one column per offset), whether each lies on the
    grid, and the distance of each offset.
    """
    d = np.arange(-radius, radius + 1)
    dx, dy = (a.ravel() for a in np.meshgrid(d, d, indexing="ij"))
    distance = np.abs(dx) + np.abs(dy)
    keep = (distance >= 1) & (distance <= radius)
    dx, dy, distance = dx[keep], dy[keep], distance[keep]
    x, y = np.divmod(np.arange(side * side), side)
    tx, ty = x[:, None] + dx, y[:, None] + dy
    inside = (tx >= 0) & (tx < side) & (ty >= 0) & (ty < side)
    return np.where(inside, tx * side + ty, 0), inside, distance


class Sugarscape(Model):
    """The grid, the sugar layer and the foragers' column table."""

    def __init__(self, side, n, params, rng):
        super().__init__(rng=rng)
        self.side, self.growback = side, params["growback"]
        self.grid = OrthogonalVonNeumannGrid(
            (side, side), torus=False, random=self.random
        )
        self.index = CellIndex(self.grid)
        self.index.track(self, Forager)
        self.capacity = landscape(
            side, params["max_sugar"], params["peaks"], params["spread"]
        )
        self.sugar = self.grid.create_property_layer("sugar", 0, dtype=np.int64)
        self.sugar[:] = self.capacity
        self.targets, self.inside, self.distance = sight(side, params["vision"][1])
        self._populate(side, n, params)
        self.history = []

    def _populate(self, side, n, params):
        rows = self.rng.choice(side * side, n, replace=False)
        traits = {
            column: self.rng.integers(params[key][0], params[key][1] + 1, n)
            for column, key in TRAITS.items()
        }
        Forager.create_agents(self, n, row=rows, **traits)

    def rankings(self, table):
        """Every forager's visible cells richer than its own, best first, end to end."""
        flat = self.sugar.reshape(-1)
        distance = self.distance
        target, inside = self.targets[table.row], self.inside[table.row]
        sugar = flat[target]
        richer = inside & (distance <= table.vision[:, None])
        richer &= sugar > flat[table.row][:, None]
        forager, slot = np.nonzero(richer)
        key = self.rng.random(forager.shape[0])
        order = np.lexsort((key, distance[slot], -sugar[forager, slot], forager))
        ends = np.cumsum(np.bincount(forager, minlength=len(table)))
        return target[forager, slot][order].tolist(), ends.tolist()

    def move(self, table):
        """Foragers in a random order each take the first free cell of their ranking."""
        ranked, ends = self.rankings(table)
        rows = table.row.tolist()
        free = (self.index.counts(table.row) == 0).tolist()
        for i in self.rng.permutation(len(rows)).tolist():
            for cell in ranked[ends[i - 1] if i else 0 : ends[i]]:
                if free[cell]:
                    free[cell], free[rows[i]] = False, True
                    rows[i] = cell
                    break
        table.row = rows

    def step(self):
        table = self.columns[Forager]
        self.move(table)
        flat = self.sugar.reshape(-1)
        table.wealth += flat[table.row] - table.metabolism
        flat[table.row] = 0
        table.remove_where(table.wealth <= 0)
        np.minimum(self.sugar + self.growback, self.capacity, out=self.sugar)
        self.history.append(len(table))


def build(seed, side, n, **params):
    """Build the model."""
    return Sugarscape(side, n, params, seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    model.run_for(steps)
    table = model.columns[Forager]
    history = model.history
    return {
        "population": len(table),
        "stats": {
            "final_population": history[-1],
            "mean_population": sum(history) / len(history),
            "mean_vision": float(table.vision.mean()),
            "mean_metabolism": float(table.metabolism.mean()),
            "mean_wealth": float(table.wealth.mean()),
            "sugar_left": int(model.sugar.sum()),
        },
    }
