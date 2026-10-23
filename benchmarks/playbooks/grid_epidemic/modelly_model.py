"""Synchronous SIR on a torus grid, written for Modelly with columnar agents.

Same model as ``mesa_model.py``. Each person's cell is a column of cell rows
(``CellIndex``), so the random walk is one ``random_neighbor`` call over the
grid's adjacency, and the infection phase is one vectorised pass: per-cell
infected counts via ``counts``, one Bernoulli draw per susceptible with
probability 1 - (1 - beta)^k, k the number of infected cellmates. No cell keeps
an agent list; nothing is updated per agent.
"""

from __future__ import annotations

import numpy as np

from modelly import Agent, Column, Model
from modelly.discrete_space import CellIndex, OrthogonalMooreGrid

S, I, R = 0, 1, 2


class Person(Agent):
    """One person; state, days and cell row live in the model's column table."""

    state = Column(np.int8, default=S)
    days = Column(np.int16, default=0)
    row = Column(np.intp, default=-1)

    def __init__(self, model, row, state):
        super().__init__(model)
        self.row = row
        self.state = state


class Epidemic(Model):
    """The grid topology, the people and the vectorised step."""

    def __init__(self, n, side, beta, recovery, initially_infected, rng):
        super().__init__(rng=rng)
        self.beta = beta
        self.recovery = recovery
        self.grid = OrthogonalMooreGrid((side, side), torus=True, random=self.random)
        self.index = CellIndex(self.grid)
        states = np.where(np.arange(n) < initially_infected, I, S)
        Person.create_agents(
            self, n, row=self.rng.integers(0, len(self.index), n), state=states
        )
        self.infected_history = []

    def step(self):
        table = self.columns[Person]
        rows = self.index.random_neighbor(table.row, self.rng)
        table.row = rows
        state = table.state
        infected = state == I
        exposure = self.index.counts(rows, infected)[rows]
        catches = (state == S) & table.draw(1.0 - (1.0 - self.beta) ** exposure)
        days = table.days
        days[infected] += 1
        recovers = infected & (days >= self.recovery)
        state[catches] = I
        state[recovers] = R
        self.infected_history.append(int((state == I).sum()))


def build(seed, n, side, beta, recovery, initially_infected):
    """Build the model."""
    return Epidemic(n, side, beta, recovery, initially_infected, seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    model.run_for(steps)
    history = model.infected_history
    state = model.columns[Person].state
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
