"""Boltzmann wealth exchange, written for Mesa 3.5 with numpy arrays.

Same model as ``mesa_model.py``, sequential order included. The
hand-vectorised Mesa baseline: a ``mesa.Model`` seeded by ``rng`` owns the
wealth as one numpy array; there are no ``Agent`` objects and no space. A step
is one vectorised pass with the law of the shuffled sequential rule
(docs/vectorised_phases.md, §8): draw the activation order and every agent's
partner up front; an agent gives iff it starts with a coin or receives one
from a giver who acts before it, which is the least fixed point of a monotone
map, reached in a few array iterations. A Mesa ``DataCollector`` records the
Gini coefficient and every agent's wealth after each step; with no agents, the
wealth is a model reporter on the array, which the collector copies.
"""

from __future__ import annotations

import mesa
import numpy as np


def gini(model):
    """Gini coefficient of the agents' wealth."""
    x = np.sort(model.wealth)
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


class Economy(mesa.Model):
    """The wealth array and the data collector."""

    def __init__(self, n, initial_wealth, rng):
        super().__init__(rng=rng)
        self.wealth = np.full(n, initial_wealth, dtype=np.int64)
        self.datacollector = mesa.DataCollector(
            model_reporters={"gini": gini, "wealth": "wealth"}
        )

    def step(self):
        wealth = self.wealth
        n = wealth.shape[0]
        turn = self.rng.permutation(n)
        partner = self.rng.integers(0, n, n)
        gives = givers(wealth > 0, partner, turn)
        self.wealth = wealth - gives + np.bincount(partner[gives], minlength=n)
        self.datacollector.collect(self)


def build(seed, n, initial_wealth):
    """Build the model."""
    return Economy(n, initial_wealth, rng=seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    for _ in range(steps):
        model.step()
    history = model.datacollector.model_vars["gini"]
    wealth = model.wealth
    return {
        "population": int(wealth.shape[0]),
        "stats": {
            "final_gini": history[-1],
            "mean_gini": sum(history) / len(history),
            "final_zero_share": float((wealth == 0).mean()),
            "final_max_wealth": int(wealth.max()),
        },
    }
