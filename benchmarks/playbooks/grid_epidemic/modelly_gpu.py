"""Synchronous SIR on a torus grid, the column variant with its steps on a GPU.

Same model and same agents as ``modelly_model.py``: ``Person`` agents with
``Column`` state, placed by a cell-row column. ``build`` creates them on the
host; the step phases run on the backend chosen by ``MODELLY_BACKEND``
(``cupy``, ``jax``, ``numpy``; ``auto`` by default, numpy when no GPU loads):
the columns as a ``DeviceTable``, the grid's adjacency as a ``DeviceCellIndex``,
the draws from a ``PhiloxStream``. ``simulate`` copies the final state back
into the agents' columns.

The infection probability ``1 - (1 - beta)^k`` is looked up in a table built
once on the host, up to the first ``k`` at which it rounds to one, so no
power function (whose last bit differs between libraries) decides a draw. With
the same seed the integer state is identical on numpy, CuPy and JAX (64-bit).
"""

from __future__ import annotations

import os

import numpy as np

from modelly import Agent, Column, Model
from modelly.gpu import DeviceCellIndex, DeviceTable, PhiloxStream, get_backend
from modelly.gpu.backend import AUTO, ENV_VARIABLE
from modelly.space import CellIndex, OrthogonalMooreGrid

S, I, R = 0, 1, 2
STEP_STREAM = 0


class Person(Agent):
    """One person; state, days and cell row live in the model's column table."""

    state = Column(np.int8, default=S)
    days = Column(np.int16, default=0)
    row = Column(np.intp, default=-1)

    def __init__(self, model, row, state):
        super().__init__(model)
        self.row = row
        self.state = state


def infection_table(beta):
    """``1 - (1 - beta)^k`` for every k until it is exactly 1.0 in float64."""
    escape, values = 1.0, []
    while 1.0 - escape != 1.0:
        values.append(1.0 - escape)
        escape *= 1.0 - beta
    return np.array([*values, 1.0])


class Epidemic(Model):
    """The grid topology, the people on the host, the steps on the device."""

    def __init__(self, n, side, beta, recovery, initially_infected, rng):
        super().__init__(rng=rng)
        self.recovery = recovery
        self.grid = OrthogonalMooreGrid((side, side), torus=True, random=self.random)
        self.index = CellIndex(self.grid)
        states = np.where(np.arange(n) < initially_infected, I, S)
        rows = self.rng.integers(0, len(self.index), n)
        Person.create_agents(self, n, row=rows, state=states)
        backend = get_backend(os.environ.get(ENV_VARIABLE, AUTO))
        self.stream = PhiloxStream(rng, STEP_STREAM, backend)
        self.cells = DeviceCellIndex(self.index, backend)
        self.people = DeviceTable.from_columns(self.columns[Person], self.stream)
        self.infect = backend.asarray(infection_table(beta))
        self.infected_history = []

    def step(self):
        xp, people = self.people.xp, self.people
        rows = self.cells.random_neighbor(people.row, self.stream)
        people.row = rows
        state = people.state
        infected = state == I
        exposure = self.cells.counts(rows, infected)[rows]
        p = self.infect[xp.minimum(exposure, self.infect.shape[0] - 1)]
        catches = (state == S) & people.draw(p)
        days = xp.where(infected, people.days + 1, people.days)
        recovers = infected & (days >= self.recovery)
        people.days = days
        people.state = xp.where(catches, I, xp.where(recovers, R, state))
        self.infected_history.append(int((people.state == I).sum()))


def build(seed, n, side, beta, recovery, initially_infected):
    """Build the model."""
    return Epidemic(n, side, beta, recovery, initially_infected, seed)


def simulate(model, steps):
    """Run ``steps`` steps, copy the state back to the agents, and summarise."""
    model.run_for(steps)
    model.people.write_to(model.columns[Person])
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
