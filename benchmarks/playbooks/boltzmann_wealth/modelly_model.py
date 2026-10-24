"""Boltzmann wealth exchange, written for Modelly with columnar agents.

Same model as ``mesa_model.py``, sequential order included. Wealth is a
column, and a step is one vectorised pass with the law of the shuffled
sequential rule (docs/vectorised_phases.md, §8): draw the activation order and
every agent's partner up front; an agent gives iff it starts with a coin or
receives one from a giver who acts before it, which is the least fixed point
of a monotone map, reached in a few array iterations. A ``DataCollector``
records the Gini coefficient and every agent's wealth after each step; the
wealth reporter is a column, so it is sliced from the table.
"""

from __future__ import annotations

import numpy as np

from modelly import Agent, Column, Model
from modelly.data.collector import DataCollector


class Person(Agent):
    """One agent; its wealth lives in the model's column table."""

    wealth = Column(np.int64, default=0)

    def __init__(self, model, wealth):
        super().__init__(model)
        self.wealth = wealth


def gini(model):
    """Gini coefficient of the agents' wealth."""
    x = np.sort(model.columns[Person].wealth)
    n = x.shape[0]
    b = float((x * (n - np.arange(n))).sum()) / (n * float(x.sum()))
    return 1 + 1 / n - 2 * b


def givers(rich, partner, turn):
    """Who gives in the sequential order ``turn``: the least fixed point from ``rich``."""
    gives = rich
    while True:
        first = np.full(turn.shape[0], turn.shape[0])
        np.minimum.at(first, partner[gives], turn[gives])
        updated = rich | (first < turn)
        if np.array_equal(updated, gives):
            return gives
        gives = updated


class Economy(Model):
    """The agents' column table and the data collector."""

    def __init__(self, n, initial_wealth, rng):
        super().__init__(rng=rng)
        Person.create_agents(self, n, wealth=[initial_wealth] * n)
        self.datacollector = DataCollector(
            model_reporters={"gini": gini}, agent_reporters={"wealth": "wealth"}
        )

    def step(self):
        table = self.columns[Person]
        wealth = table.wealth
        n = wealth.shape[0]
        turn = self.rng.permutation(n)
        partner = self.rng.integers(0, n, n)
        gives = givers(wealth > 0, partner, turn)
        table.wealth = wealth - gives + np.bincount(partner[gives], minlength=n)
        self.datacollector.collect(self)


def build(seed, n, initial_wealth):
    """Build the model."""
    return Economy(n, initial_wealth, seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    model.run_for(steps)
    history = model.datacollector.model_vars["gini"]
    wealth = model.columns[Person].wealth
    return {
        "population": int(wealth.shape[0]),
        "stats": {
            "final_gini": history[-1],
            "mean_gini": sum(history) / len(history),
            "final_zero_share": float((wealth == 0).mean()),
            "final_max_wealth": int(wealth.max()),
        },
    }
