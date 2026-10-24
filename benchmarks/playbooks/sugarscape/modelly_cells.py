"""Sugarscape with constant growback, written for Modelly with agents held in cells.

Same model as ``mesa_model.py``, with the same data structure as Mesa: a von
Neumann grid with a ``sugar`` property layer and at most one forager per cell
(``capacity=1``). Each forager scans ``cell.get_neighborhood(radius=vision)``
(cached per cell and radius) for the best free cell and reads its sugar through
the layer's cell accessor; the growback is one numpy operation on the layer.
"""

from __future__ import annotations

import numpy as np

from modelly import Column, Model
from modelly.space import CellAgent, OrthogonalVonNeumannGrid


class Forager(CellAgent):
    """Sees, moves, eats, starves; its traits live in the model's column table."""

    vision = Column(np.int64, default=1)
    metabolism = Column(np.int64, default=1)
    wealth = Column(np.int64, default=0)

    def __init__(self, model, cell, vision, metabolism, wealth):
        super().__init__(model)
        self.cell = cell
        self.vision = vision
        self.metabolism = metabolism
        self.wealth = wealth

    def best_cells(self):
        """The nearest free cells in sight holding the most sugar, if more than here."""
        here = self.cell
        best, most, nearest = [], here.sugar, 0
        x, y = here.coordinate
        for cell in here.get_neighborhood(radius=self.vision):
            if not cell.is_empty:
                continue
            sugar = cell.sugar
            if sugar < most:
                continue
            cx, cy = cell.coordinate
            distance = abs(cx - x) + abs(cy - y)
            if sugar > most or distance < nearest:
                best, most, nearest = [cell], sugar, distance
            elif distance == nearest:
                best.append(cell)
        return best

    def step(self):
        best = self.best_cells()
        if best:
            self.cell = self.random.choice(best)
        cell = self.cell
        self.wealth += int(cell.sugar) - self.metabolism
        cell.sugar = 0
        if self.wealth <= 0:
            self.remove()


def landscape(side, max_sugar, peaks, spread):
    """Sugar capacity of every cell: Gaussian hills rounded to whole units."""
    x = (np.arange(side) + 0.5) / side
    xx, yy = np.meshgrid(x, x, indexing="ij")
    hills = [
        np.exp(-((xx - px) ** 2 + (yy - py) ** 2) / (2 * spread**2)) for px, py in peaks
    ]
    return np.rint(max_sugar * np.maximum.reduce(hills)).astype(np.int64)


class Sugarscape(Model):
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
        self.sugar = self.grid.create_property_layer("sugar", 0, dtype=np.int64)
        self.sugar[:] = self.capacity
        self._populate(side, n, params)
        self.history = []

    def _populate(self, side, n, params):
        cells = self.rng.choice(side * side, n, replace=False).tolist()
        traits = [
            self.rng.integers(lo, hi + 1, n).tolist()
            for lo, hi in (params[k] for k in ("vision", "metabolism", "initial_sugar"))
        ]
        for cell, *trait in zip(cells, *traits):
            Forager(self, self.grid[divmod(cell, side)], *trait)

    def step(self):
        self.agents.shuffle_do("step")
        np.minimum(self.sugar + self.growback, self.capacity, out=self.sugar)
        self.history.append(len(self.agents))


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
