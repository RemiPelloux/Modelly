"""Boltzmann wealth exchange, written for mesa-frames.

Same model as ``mesa_model.py``, sequential order included. The agents are one
``AgentSet`` whose polars frame holds the wealth column, and a step is one
vectorised pass with the law of the shuffled sequential rule
(docs/vectorised_phases.md, §8): draw the activation order and every agent's
partner up front; an agent gives iff it starts with a coin or receives one
from a giver who acts before it, the least fixed point of a monotone map,
reached in a few group-by/join rounds. (The mesa-frames example of this model
lets every rich agent give at once, which is a different law.) A mesa-frames
``DataCollector`` records the Gini coefficient and every agent's wealth after
each step, in memory.
"""

from __future__ import annotations

import numpy as np
import polars as pl
from mesa_frames import AgentSet, DataCollector, Model


def gini(model):
    """Gini coefficient of the agents' wealth."""
    x = model.sets["People"].df["wealth"].sort()
    n = x.len()
    b = float((x * pl.Series(np.arange(n, 0, -1))).sum()) / (n * float(x.sum()))
    return 1 + 1 / n - 2 * b


def first_gift(draws, gives):
    """Earliest turn at which each agent receives a coin from a giver."""
    first = (
        draws.filter(gives).group_by("partner").agg(pl.col("turn").min().alias("first"))
    )
    return draws.join(
        first, left_on="i", right_on="partner", how="left", maintain_order="left"
    )["first"]


def givers(draws):
    """Who gives in the sequential order ``turn``: the least fixed point from ``rich``."""
    rich, turn = draws["rich"], draws["turn"]
    gives = rich
    while True:
        updated = rich | (first_gift(draws, gives) < turn).fill_null(False)
        if updated.equals(gives):
            return gives
        gives = updated


class People(AgentSet):
    """Every agent's wealth, one row each."""

    def __init__(self, model, n, initial_wealth):
        super().__init__(model)
        self += pl.DataFrame({"wealth": np.full(n, initial_wealth, dtype=np.int64)})

    def step(self):
        n = len(self)
        draws = pl.DataFrame(
            {
                "i": np.arange(n),
                "turn": self.random.permutation(n),
                "partner": self.random.integers(0, n, n),
                "rich": self.df["wealth"] > 0,
            }
        )
        gives = givers(draws)
        received = draws.filter(gives).group_by("partner").len()
        gained = draws.join(
            received, left_on="i", right_on="partner", how="left", maintain_order="left"
        )["len"].fill_null(0)
        self["wealth"] = self.df["wealth"] - gives.cast(pl.Int64) + gained


class Economy(Model):
    """The agent set and the data collector."""

    def __init__(self, n, initial_wealth, seed):
        super().__init__(seed)
        self.sets += People(self, n, initial_wealth)
        self.datacollector = DataCollector(
            model=self,
            model_reporters={"gini": gini},
            agent_reporters={"wealth": "wealth"},
            storage="memory",
        )

    def step(self):
        self.sets.do("step")
        self.datacollector.collect()


def build(seed, n, initial_wealth):
    """Build the model."""
    return Economy(n, initial_wealth, seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    for _ in range(steps):
        model.step()
    history = model.datacollector.data["model"]["gini"]
    wealth = model.sets["People"].df["wealth"]
    return {
        "population": wealth.len(),
        "stats": {
            "final_gini": float(history[-1]),
            "mean_gini": float(history.mean()),
            "final_zero_share": float((wealth == 0).mean()),
            "final_max_wealth": int(wealth.max()),
        },
    }
