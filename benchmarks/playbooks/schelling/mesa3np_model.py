"""Schelling segregation on a torus grid, written for Mesa 3.5 with numpy arrays.

Same model as ``mesa_model.py``. The hand-vectorised Mesa baseline: a
``mesa.Model`` seeded by ``rng`` owns the residents as numpy arrays (kind and
the flat index of each resident's cell); there are no ``Agent`` objects. The
space is Mesa's ``OrthogonalMooreGrid`` with capacity one: its cell
connections are read once into an (cells, 8) neighbour table, and its
``PropertyLayer``s hold the occupancy, the built-in ``empty`` layer and a
``kind`` layer (-1 for an empty cell), kept in step with the moves. The
happiness phase is one gather of the ``kind`` layer over every resident's
neighbours. The moves are one vectorised pass with the law of the sequential
rule (docs/vectorised_phases.md, §7): while the unhappy residents move one at
a time to a uniformly random empty cell, the number of empty cells never
changes, so each mover draws a slot of a fixed-size pool of empty cells and
leaves its old cell in that slot for the next mover who draws it.
"""

from __future__ import annotations

import mesa
import numpy as np
from mesa.discrete_space import OrthogonalMooreGrid

EMPTY, MAJORITY, MINORITY = -1, 0, 1


def neighbour_table(grid):
    """Flat indices of every cell's neighbours, from the grid's own connections."""
    width = grid.dimensions[1]
    return np.array(
        [
            [
                n.coordinate[0] * width + n.coordinate[1]
                for n in cell.connections.values()
            ]
            for cell in grid.all_cells
        ],
        dtype=np.intp,
    )


class Schelling(mesa.Model):
    """The grid, its occupancy layers, the resident arrays and the vectorised step."""

    def __init__(self, side, density, minority, homophily, rng):
        super().__init__(rng=rng)
        self.homophily = homophily
        self.grid = OrthogonalMooreGrid(
            (side, side), torus=True, capacity=1, random=self.random
        )
        self.neighbours = neighbour_table(self.grid)
        self.cell = np.flatnonzero(self.rng.random(side * side) < density)
        minority_draw = self.rng.random(self.cell.shape[0]) < minority
        self.kind = np.where(minority_draw, MINORITY, MAJORITY).astype(np.int8)
        self.layer = self.grid.create_property_layer("kind", EMPTY, dtype=np.int8)
        self.kinds = self.layer.data.reshape(-1)
        self.empty = self.grid.empty.data.reshape(-1)
        self.kinds[self.cell] = self.kind
        self.empty[self.cell] = False
        self.history = []

    def neighbours_of_residents(self):
        """Same-kind and all neighbours of every resident."""
        around = self.kinds[self.neighbours[self.cell]]
        similar = (around == self.kind[:, None]).sum(axis=1)
        return similar, (around != EMPTY).sum(axis=1)

    def relocate(self, movers):
        """Every mover takes a uniformly random empty cell, in a random order."""
        pool = np.flatnonzero(self.empty)
        if movers.shape[0] == 0 or pool.shape[0] == 0:
            return
        movers = self.rng.permutation(movers)
        slots = self.rng.integers(0, pool.shape[0], movers.shape[0])
        order = np.argsort(slots, kind="stable")
        movers, slots = movers[order], slots[order]
        old = self.cell[movers]
        first = np.ones(movers.shape[0], dtype=bool)
        first[1:] = slots[1:] != slots[:-1]
        new = np.where(first, pool[slots], np.roll(old, 1))
        self.kinds[old], self.empty[old] = EMPTY, True
        self.kinds[new], self.empty[new] = self.kind[movers], False
        self.cell[movers] = new

    def step(self):
        similar, _ = self.neighbours_of_residents()
        movers = np.flatnonzero(similar < self.homophily)
        self.relocate(movers)
        n = self.cell.shape[0]
        self.history.append((1 - movers.shape[0] / n, movers.shape[0]))


def build(seed, side, density, minority, homophily):
    """Build the model."""
    return Schelling(side, density, minority, homophily, rng=seed)


def segregation(model):
    """Mean share of same-kind neighbours, over residents with any neighbour."""
    similar, around = model.neighbours_of_residents()
    some = around > 0
    return float((similar[some] / around[some]).mean())


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    for _ in range(steps):
        model.step()
    happy = [h[0] for h in model.history]
    moves = [h[1] for h in model.history]
    return {
        "population": int(model.cell.shape[0]),
        "stats": {
            "final_happy": happy[-1],
            "mean_happy": sum(happy) / len(happy),
            "total_moves": sum(moves),
            "segregation": segregation(model),
        },
    }
