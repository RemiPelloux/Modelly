"""Schelling segregation on a torus grid, written for mesa-frames.

Same model as ``mesa_model.py``. The residents are one ``AgentSet`` (kind and
happiness columns) placed on a mesa-frames ``Grid`` of capacity one. The
happiness phase is a polars cross join of every resident with the eight Moore
offsets, wrapped by ``Grid.torus_adj``, joined to the occupants and grouped
per resident. (``Grid.get_neighborhood`` is not used: on a torus it drops
duplicate cells across all centres, so two residents sharing a neighbour cell
lose one of the rows.) The moves are one vectorised pass with the law of the
sequential rule (docs/vectorised_phases.md, §7): while the unhappy residents
move one at a time to a uniformly random empty cell, the number of empty cells
never changes, so each mover draws a slot of a fixed-size pool of empty cells
and leaves its old cell in that slot for the next mover who draws it; the
result goes to ``Grid.move_agents`` in one call. (``Grid.move_to_empty``
samples distinct cells among those empty before anyone moves, so a mover
never takes a cell another mover just left: a different law.)
"""

from __future__ import annotations

import numpy as np
import polars as pl
from mesa_frames import AgentSet, Grid, Model

MOORE = pl.DataFrame(
    {"d0": [-1, -1, -1, 0, 0, 1, 1, 1], "d1": [-1, 0, 1, -1, 1, -1, 0, 1]}
)
CELL = ["dim_0", "dim_1"]


class Residents(AgentSet):
    """One row per resident: kind 0 (majority) or 1 (minority), and happiness."""

    def __init__(self, model, kinds):
        super().__init__(model)
        self += pl.DataFrame({"kind": kinds, "happy": np.zeros(kinds.shape[0], bool)})

    def neighbours(self):
        """Same-kind (``similar``) and all (``around``) neighbours of every resident."""
        here = self.pos.join(self.df.select("unique_id", "kind"), on="unique_id")
        offsets = here.join(MOORE, how="cross").select(
            "unique_id",
            "kind",
            pl.col("dim_0") + pl.col("d0"),
            pl.col("dim_1") + pl.col("d1"),
        )
        offsets = offsets.with_columns(self.space.torus_adj(offsets.select(CELL)))
        occupants = here.select(*CELL, pl.col("kind").alias("other"))
        counts = (
            offsets.join(occupants, on=CELL)
            .group_by("unique_id")
            .agg(
                similar=(pl.col("other") == pl.col("kind")).sum(),
                around=pl.len(),
            )
        )
        return (
            self.df.select("unique_id")
            .join(counts, on="unique_id", how="left", maintain_order="left")
            .fill_null(0)
        )

    def assess(self):
        """Happy when at least ``homophily`` neighbours are of the same kind."""
        self["happy"] = self.neighbours()["similar"] >= self.model.homophily

    def relocate(self):
        """Every unhappy resident takes a uniformly random empty cell, in a random order."""
        pos = self.pos.filter(~self.df["happy"])
        pool = self.space.empty_cells.select(CELL)
        if pos.height == 0 or pool.height == 0:
            return
        pos = pos[self.random.permutation(pos.height)]
        slots = pl.Series("slot", self.random.integers(0, pool.height, pos.height))
        moves = pos.with_columns(slots).sort("slot", maintain_order=True)
        first = moves["slot"] != moves["slot"].shift(1)
        target = pool[moves["slot"]]
        new = moves.select(
            pl.when(first.fill_null(True))
            .then(target[c])
            .otherwise(pl.col(c).shift(1))
            .alias(c)
            for c in CELL
        )
        self.space.move_agents(moves["unique_id"], new)

    def step(self):
        """Everyone assesses at once, then the unhappy move."""
        self.assess()
        self.relocate()


class Schelling(Model):
    """The grid, the residents and the two-phase step."""

    def __init__(self, side, density, minority, homophily, seed):
        super().__init__(seed)
        self.homophily = homophily
        self.space = Grid(self, [side, side], torus=True, capacity=1)
        occupied = np.flatnonzero(self.random.random(side * side) < density)
        kinds = (self.random.random(occupied.shape[0]) < minority).astype(np.int8)
        residents = Residents(self, kinds)
        self.sets += residents
        cells = pl.DataFrame({"dim_0": occupied // side, "dim_1": occupied % side})
        self.space.place_agents(residents, cells)
        self.history = []

    def step(self):
        self.sets.do("step")
        residents = self.sets["Residents"]
        moves = int((~residents.df["happy"]).sum())
        self.history.append((1 - moves / len(residents), moves))


def build(seed, side, density, minority, homophily):
    """Build the model."""
    return Schelling(side, density, minority, homophily, seed)


def segregation(model):
    """Mean share of same-kind neighbours, over residents with any neighbour."""
    counts = model.sets["Residents"].neighbours().filter(pl.col("around") > 0)
    return float((counts["similar"] / counts["around"]).mean())


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    for _ in range(steps):
        model.step()
    happy = [h[0] for h in model.history]
    moves = [h[1] for h in model.history]
    return {
        "population": len(model.sets["Residents"]),
        "stats": {
            "final_happy": happy[-1],
            "mean_happy": sum(happy) / len(happy),
            "total_moves": sum(moves),
            "segregation": segregation(model),
        },
    }
