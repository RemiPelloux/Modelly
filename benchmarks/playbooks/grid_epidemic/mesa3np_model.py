"""Synchronous SIR on a torus grid, written for Mesa 3.5 with numpy arrays.

Same model as ``mesa_model.py``. The hand-vectorised Mesa baseline: a
``mesa.Model`` seeded by ``rng`` owns the population as numpy arrays (state,
days and the flat index of each person's cell) and updates them with array
operations; there are no ``Agent`` objects. The space is Mesa's
``OrthogonalMooreGrid``: its cell connections are read once into an
(cells, 8) neighbour table, so the random walk is one gather, and the infected
count per cell is the grid's ``infected`` ``PropertyLayer``, rebuilt by one
``bincount`` per step. A susceptible with ``k`` infected cellmates catches the
infection with probability 1 - (1 - beta)^k, one draw per susceptible, which is
the law of ``k`` independent Bernoulli(beta) trials of the reference.
"""

from __future__ import annotations

import mesa
import numpy as np
from mesa.discrete_space import OrthogonalMooreGrid

S, I, R = 0, 1, 2


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


class Epidemic(mesa.Model):
    """The grid, the population arrays and the vectorised step."""

    def __init__(self, n, side, beta, recovery, initially_infected, rng):
        super().__init__(rng=rng)
        self.beta = beta
        self.recovery = recovery
        self.grid = OrthogonalMooreGrid((side, side), torus=True, random=self.random)
        self.infected = self.grid.create_property_layer("infected", 0, dtype=np.int64)
        self.neighbours = neighbour_table(self.grid)
        self.cell = self.rng.integers(0, side * side, n)
        self.state = np.where(np.arange(n) < initially_infected, I, S).astype(np.int8)
        self.days = np.zeros(n, dtype=np.int16)
        self.infected_history = []

    def step(self):
        n, cells = self.cell.shape[0], self.neighbours.shape[0]
        moves = self.rng.integers(0, self.neighbours.shape[1], n)
        self.cell = cell = self.neighbours[self.cell, moves]
        state = self.state
        infected = state == I
        counts = np.bincount(cell[infected], minlength=cells)
        self.infected.data = counts.reshape(self.infected.dimensions)
        exposure = counts[cell]
        escape = (1.0 - self.beta) ** exposure
        catches = (state == S) & (self.rng.random(n) >= escape)
        self.days[infected] += 1
        recovers = infected & (self.days >= self.recovery)
        state[catches] = I
        state[recovers] = R
        self.infected_history.append(int((state == I).sum()))


def build(seed, n, side, beta, recovery, initially_infected):
    """Build the model."""
    return Epidemic(n, side, beta, recovery, initially_infected, rng=seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    for _ in range(steps):
        model.step()
    history = model.infected_history
    state = model.state
    peak = max(history)
    return {
        "population": int(state.shape[0]),
        "stats": {
            "final_S": int((state == S).sum()),
            "final_I": int((state == I).sum()),
            "final_R": int((state == R).sum()),
            "peak_I": peak,
            "peak_step": history.index(peak) + 1,
            "mean_I": sum(history) / len(history),
        },
    }
