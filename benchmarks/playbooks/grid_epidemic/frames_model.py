"""Synchronous SIR on a torus grid, written for mesa-frames.

Same model as ``mesa_model.py``. The people are one ``AgentSet`` whose polars
frame holds ``state`` and ``days``; their cells live in a mesa-frames ``Grid``
(torus, unlimited capacity). The random walk is one ``move_agents`` call with a
random Moore offset per person, wrapped by ``torus_adj``. The infection phase
is one polars pass: the infected count of every cell by a window over the
cell coordinates, one Bernoulli draw per person with probability
1 - (1 - beta)^k, k the number of infected cellmates (the same law as k
independent trials), and recovery as a column expression, all from the states
at the start of the phase.

``Grid.get_neighborhood`` is not used for the walk: on a torus it drops the
duplicate cells of the whole frame, not of each centre, so two people with a
neighbour cell in common lose it from one of their neighbourhoods.
"""

from __future__ import annotations

import numpy as np
import polars as pl
from mesa_frames import AgentSet, Grid, Model

S, I, R = 0, 1, 2
# the eight Moore offsets
DX = np.array([-1, -1, -1, 0, 0, 1, 1, 1])
DY = np.array([-1, 0, 1, -1, 1, -1, 0, 1])
CELL = ["dim_0", "dim_1"]


class People(AgentSet):
    """Every person as one row: ``state`` and ``days`` infected."""

    def __init__(self, model, n, initially_infected):
        super().__init__(model)
        states = np.where(np.arange(n) < initially_infected, I, S)
        self += pl.DataFrame(
            {
                "state": pl.Series(states, dtype=pl.Int8),
                "days": pl.Series(np.zeros(n), dtype=pl.Int16),
            }
        )

    def step(self):
        self.move()
        self.expose()

    def move(self):
        """Every person steps to a uniformly random Moore neighbour cell."""
        pos = self.pos
        pick = self.random.integers(0, len(DX), pos.height)
        dest = pos.select(
            pl.col("dim_0") + pl.Series(DX[pick]),
            pl.col("dim_1") + pl.Series(DY[pick]),
        )
        self.space.move_agents(pos["unique_id"], self.space.torus_adj(dest))

    def expose(self):
        """Infect, count days and recover, all from the start-of-phase states."""
        model = self.model
        state, days = pl.col("state"), pl.col("days")
        infected = state == I
        k = infected.cast(pl.Int32).sum().over(CELL)
        catches = (state == S) & (pl.col("u") < 1.0 - (1.0 - model.beta) ** k)
        new_days = pl.when(infected).then(days + 1).otherwise(days)
        recovers = infected & (new_days >= model.recovery)
        frame = self.df.join(self.pos, on="unique_id", maintain_order="left")
        frame = frame.with_columns(u=pl.Series(self.random.random(frame.height)))
        self.df = frame.select(
            "unique_id",
            pl.when(catches)
            .then(I)
            .when(recovers)
            .then(R)
            .otherwise(state)
            .cast(pl.Int8)
            .alias("state"),
            new_days.cast(pl.Int16),
        )


class Epidemic(Model):
    """The torus grid, the people and the step."""

    def __init__(self, n, side, beta, recovery, initially_infected, seed):
        super().__init__(seed)
        self.beta, self.recovery = beta, recovery
        self.space = Grid(self, [side, side], torus=True, neighborhood_type="moore")
        people = People(self, n, initially_infected)
        self.sets += people
        coords = self.random.integers(0, side, (n, 2))
        self.space.place_agents(people, pl.DataFrame(coords, schema=CELL))
        self.infected_history = []

    def step(self):
        people = self.sets[0]
        people.step()
        self.infected_history.append(int((people.df["state"] == I).sum()))


def build(seed, n, side, beta, recovery, initially_infected):
    """Build the model."""
    return Epidemic(n, side, beta, recovery, initially_infected, seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    for _ in range(steps):
        model.step()
    history = model.infected_history
    state = model.sets[0].df["state"]
    peak = max(history)
    return {
        "population": state.len(),
        "stats": {
            "final_S": int((state == S).sum()),
            "final_I": int((state == I).sum()),
            "final_R": int((state == R).sum()),
            "peak_I": peak,
            "peak_step": history.index(peak) + 1,
            "mean_I": sum(history) / len(history),
        },
    }
