"""Sugarscape with constant growback, written for mesa-frames.

Same model as ``mesa_model.py``. The foragers are one ``AgentSet`` whose polars
frame holds ``vision``, ``metabolism`` and ``wealth``; the landscape is the
``sugar`` and ``max_sugar`` columns of a mesa-frames ``Grid`` (capacity 1, not
a torus). Every step the set is shuffled (the activation order, as in
mesa-frames' own Sugarscape), and all the looking is one polars pass: every
forager's visible cells, their start-of-step sugar and its ranking of the cells
richer than its own by sugar, then distance, then a random key. Only who takes
which cell stays sequential: one plain loop walks the foragers in order, each
taking the first free cell of its ranking (docs/vectorised_phases.md, §9, of
the Modelly repository: the same law as Mesa's one-at-a-time update, since no
forager's choice depends on sugar eaten before its turn). Eating, burning,
starving and regrowth are column operations after the loop.

Two departures from mesa-frames' own example, both needed for this rule. Its
lottery-in-rounds conflict resolution has a different law from a random
sequential order, so the walk replaces it. ``Grid.get_neighborhood`` with a von
Neumann radius r returns only the 4r cells along the axes, not Mesa's diamond,
so the sight is a precomputed diamond of offsets cross-joined to the foragers.
"""

from __future__ import annotations

import numpy as np
import polars as pl
from mesa_frames import AgentSet, Grid, Model

CELL = ["dim_0", "dim_1"]
TRAITS = {"vision": "vision", "metabolism": "metabolism", "wealth": "initial_sugar"}


def landscape(side, max_sugar, peaks, spread):
    """Sugar capacity of every cell: Gaussian hills rounded to whole units."""
    x = (np.arange(side) + 0.5) / side
    xx, yy = np.meshgrid(x, x, indexing="ij")
    hills = [
        np.exp(-((xx - px) ** 2 + (yy - py) ** 2) / (2 * spread**2)) for px, py in peaks
    ]
    return np.rint(max_sugar * np.maximum.reduce(hills)).astype(np.int64)


def sight(radius):
    """The von Neumann offsets at distance 1 to ``radius`` (a diamond)."""
    d = np.arange(-radius, radius + 1)
    dx, dy = (a.ravel() for a in np.meshgrid(d, d, indexing="ij"))
    distance = np.abs(dx) + np.abs(dy)
    keep = (distance >= 1) & (distance <= radius)
    return pl.DataFrame({"dx": dx[keep], "dy": dy[keep], "distance": distance[keep]})


class Foragers(AgentSet):
    """Every forager as one row: ``vision``, ``metabolism`` and ``wealth``."""

    def __init__(self, model, traits):
        super().__init__(model)
        self += pl.DataFrame(traits)
        # The mask of an AgentSet created empty stays a length-0 Series after
        # ``add``, and ``discard`` then fails on it; select all to rebuild it.
        self.select()

    def step(self):
        self.shuffle(inplace=True)
        self.move()
        self.eat()
        self.starve()

    def origins(self, sugar):
        """Every forager in activation order (``order``): its cell and its sugar."""
        return (
            self.df.select("unique_id", "vision")
            .with_row_index("order")
            .join(self.pos, on="unique_id", maintain_order="left")
            .join(sugar, on=CELL, maintain_order="left")
            .rename({"sugar": "own"})
        )

    def rankings(self, origins, sugar):
        """Every forager's visible cells richer than its own, best first.

        Rows are in activation order, then by sugar (most first), distance
        (nearest first) and a uniform key, which breaks the ties.
        """
        seen = (
            origins.join(self.model.sight, how="cross", maintain_order="left")
            .filter(pl.col("distance") <= pl.col("vision"))
            .select(
                "order",
                "own",
                "distance",
                pl.col("dim_0") + pl.col("dx"),
                pl.col("dim_1") + pl.col("dy"),
            )
            .join(sugar, on=CELL, maintain_order="left")  # inner: drops off-grid
            .filter(pl.col("sugar") > pl.col("own"))
        )
        seen = seen.with_columns(key=pl.Series(self.random.random(seen.height)))
        return seen.sort(
            ["order", "sugar", "distance", "key"],
            descending=[False, True, False, False],
        )

    def move(self):
        """Foragers in order each take the first free cell of their ranking."""
        side = self.model.side
        sugar = self.space.cells.select(*CELL, "sugar")
        origins = self.origins(sugar)
        ranked = self.rankings(origins, sugar)
        rows = (origins["dim_0"] * side + origins["dim_1"]).to_numpy()
        free = np.ones(side * side, dtype=bool)
        free[rows] = False
        ends = np.cumsum(np.bincount(ranked["order"], minlength=len(rows)))
        cell = (ranked["dim_0"] * side + ranked["dim_1"]).to_list()
        new = np.asarray(walk(rows.tolist(), cell, ends.tolist(), free.tolist()))
        moved = np.flatnonzero(new != rows)
        if moved.size:
            x, y = np.divmod(new[moved], side)
            ids = origins["unique_id"].gather(moved)
            self.space.move_agents(ids, pl.DataFrame({"dim_0": x, "dim_1": y}))

    def eat(self):
        """Every forager eats all the sugar of its cell and burns its metabolism."""
        here = self.pos.join(
            self.space.cells.select(*CELL, "sugar"), on=CELL, maintain_order="left"
        )
        self.df = (
            self.df.join(
                here.select("unique_id", "sugar"), on="unique_id", maintain_order="left"
            )
            .with_columns(
                wealth=pl.col("wealth") + pl.col("sugar") - pl.col("metabolism")
            )
            .drop("sugar")
        )
        self.space.set_cells(here.select(CELL), {"sugar": np.zeros(here.height, int)})

    def starve(self):
        """Foragers whose store is spent leave the grid and the model."""
        starved = self.df.filter(pl.col("wealth") <= 0)["unique_id"]
        if starved.len():
            self.space.remove_agents(starved)  # AgentSet.discard leaves them placed
            self.discard(starved)


def walk(rows, cell, ends, free):
    """The sequential phase: forager i takes its first free ranked cell, in order."""
    start = 0
    for i, end in enumerate(ends):
        for c in cell[start:end]:
            if free[c]:
                free[c], free[rows[i]] = False, True
                rows[i] = c
                break
        start = end
    return rows


class Sugarscape(Model):
    """The grid with its sugar columns, and the foragers."""

    def __init__(self, side, n, params, seed):
        super().__init__(seed)
        self.side, self.growback = side, params["growback"]
        self.sight = sight(params["vision"][1])
        capacity = landscape(
            side, params["max_sugar"], params["peaks"], params["spread"]
        ).ravel()
        x, y = np.divmod(np.arange(side * side), side)
        self.space = Grid(
            self, [side, side], capacity=1, neighborhood_type="von_neumann"
        )
        self.space.set_cells(
            pl.DataFrame(
                {"dim_0": x, "dim_1": y, "sugar": capacity, "max_sugar": capacity}
            )
        )
        self._populate(side, n, params)
        self.history = []

    def _populate(self, side, n, params):
        cells = self.random.choice(side * side, n, replace=False)
        traits = {
            column: self.random.integers(params[key][0], params[key][1] + 1, n)
            for column, key in TRAITS.items()
        }
        foragers = Foragers(self, traits)
        self.sets += foragers
        x, y = np.divmod(cells, side)
        self.space.place_agents(foragers, pl.DataFrame({"dim_0": x, "dim_1": y}))

    def step(self):
        foragers = self.sets[0]
        foragers.step()
        cells = self.space.cells.select(*CELL, "sugar", "max_sugar")
        sugar = pl.min_horizontal(pl.col("sugar") + self.growback, pl.col("max_sugar"))
        self.space.set_cells(cells.select(*CELL, sugar=sugar))
        self.history.append(len(foragers))


def build(seed, side, n, **params):
    """Build the model."""
    return Sugarscape(side, n, params, seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    for _ in range(steps):
        model.step()
    df = model.sets[0].df
    history = model.history
    return {
        "population": df.height,
        "stats": {
            "final_population": history[-1],
            "mean_population": sum(history) / len(history),
            "mean_vision": float(df["vision"].mean()),
            "mean_metabolism": float(df["metabolism"].mean()),
            "mean_wealth": float(df["wealth"].mean()),
            "sugar_left": int(model.space.cells["sugar"].sum()),
        },
    }
