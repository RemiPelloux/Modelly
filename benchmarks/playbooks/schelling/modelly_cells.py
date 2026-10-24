"""Schelling segregation on a torus grid, written for Modelly with agents held in cells.

Same model as ``mesa_model.py``, with the same data structure as Mesa: every
cell holds at most one resident (``capacity=1``), and the unhappy residents
move one at a time to ``select_random_empty_cell``, which the grid answers from
its index of empty cells in O(1). The happiness phase is vectorised: residents
of each kind per cell (``CellIndex.counts``), summed over the Moore neighbours
(``neighbor_sum``).
"""

from __future__ import annotations

import numpy as np

from modelly import Column, Model
from modelly.space import CellAgent, CellIndex, OrthogonalMooreGrid


class Resident(CellAgent):
    """One resident; kind and cell row live in the model's column table."""

    kind = Column(np.int8, default=0)
    row = Column(np.intp, default=-1)

    def __init__(self, model, cell, kind):
        super().__init__(model)
        self.cell = cell
        self.row = cell.index
        self.kind = kind

    def relocate(self):
        cell = self.model.grid.select_random_empty_cell()
        self.cell = cell
        self.row = cell.index


class Schelling(Model):
    """The grid, the residents and the step."""

    def __init__(self, side, density, minority, homophily, rng):
        super().__init__(rng=rng)
        self.homophily = homophily
        self.grid = OrthogonalMooreGrid(
            (side, side), torus=True, capacity=1, random=self.random
        )
        self.index = CellIndex(self.grid)
        occupied = np.flatnonzero(self.rng.random(len(self.index)) < density)
        kinds = self.rng.random(occupied.shape[0]) < minority
        cells = self.index.cells
        for row, kind in zip(occupied.tolist(), kinds.tolist()):
            Resident(self, cells[row], kind)
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

    def step(self):
        table = self.columns[Resident]
        similar, _ = self.neighbours(table)
        unhappy = similar < self.homophily
        moves = int(unhappy.sum())
        table.where(unhappy).shuffle_do("relocate")
        self.history.append((1 - moves / len(table), moves))


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
