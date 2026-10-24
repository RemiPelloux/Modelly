"""Schelling segregation on a torus grid, written for Modelly with columnar agents.

Same model as ``mesa_model.py``. Each resident's cell is a column of cell rows
(``CellIndex``), so the happiness phase is two sparse products: residents of
each kind per cell (``counts``), summed over the Moore neighbours
(``neighbor_sum``). The moves are one vectorised pass with the law of the
sequential rule (docs/vectorised_phases.md, §7): while the unhappy residents
move one at a time to a uniformly random empty cell, the number of empty cells
never changes, so each mover draws a slot of a fixed-size pool of empty cells
and leaves its old cell in that slot for the next mover who draws it.
"""

from __future__ import annotations

import numpy as np

from modelly import Agent, Column, Model
from modelly.space import CellIndex, OrthogonalMooreGrid


class Resident(Agent):
    """One resident; kind and cell row live in the model's column table."""

    kind = Column(np.int8, default=0)
    row = Column(np.intp, default=-1)

    def __init__(self, model, row, kind):
        super().__init__(model)
        self.row = row
        self.kind = kind


class Schelling(Model):
    """The grid topology, the residents and the vectorised step."""

    def __init__(self, side, density, minority, homophily, rng):
        super().__init__(rng=rng)
        self.homophily = homophily
        self.grid = OrthogonalMooreGrid((side, side), torus=True, random=self.random)
        self.index = CellIndex(self.grid)
        self.index.track(self, Resident)
        occupied = np.flatnonzero(self.rng.random(len(self.index)) < density)
        kinds = self.rng.random(occupied.shape[0]) < minority
        Resident.create_agents(self, occupied.shape[0], row=occupied, kind=kinds)
        self.history = []

    def neighbours(self, table):
        """Same-kind and all neighbours of every resident."""
        rows, minority = table.row, table.kind == 1
        around_minority = self.index.neighbor_sum(self.index.counts(rows, minority))
        around = self.index.neighbor_sum(self.index.counts(rows))
        mine = np.where(
            minority, around_minority[rows], around[rows] - around_minority[rows]
        )
        return mine, around[rows]

    def relocate(self, table, movers):
        """Every mover takes a uniformly random empty cell, in a random order."""
        pool = np.flatnonzero(self.index.counts(table.row) == 0)
        if movers.shape[0] == 0 or pool.shape[0] == 0:
            return
        movers = self.rng.permutation(movers)
        slots = self.rng.integers(0, pool.shape[0], movers.shape[0])
        order = np.argsort(slots, kind="stable")
        movers, slots = movers[order], slots[order]
        old = table.row[movers]
        first = np.ones(movers.shape[0], dtype=bool)
        first[1:] = slots[1:] != slots[:-1]
        table.row[movers] = np.where(first, pool[slots], np.roll(old, 1))

    def step(self):
        table = self.columns[Resident]
        similar, _ = self.neighbours(table)
        movers = np.flatnonzero(similar < self.homophily)
        self.relocate(table, movers)
        self.history.append((1 - movers.shape[0] / len(table), movers.shape[0]))


def build(seed, side, density, minority, homophily):
    """Build the model."""
    return Schelling(side, density, minority, homophily, seed)


def segregation(model):
    """Mean share of same-kind neighbours, over residents with any neighbour."""
    similar, around = model.neighbours(model.columns[Resident])
    some = around > 0
    return float((similar[some] / around[some]).mean())


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    model.run_for(steps)
    happy = [h[0] for h in model.history]
    moves = [h[1] for h in model.history]
    return {
        "population": len(model.columns[Resident]),
        "stats": {
            "final_happy": happy[-1],
            "mean_happy": sum(happy) / len(happy),
            "total_moves": sum(moves),
            "segregation": segregation(model),
        },
    }
