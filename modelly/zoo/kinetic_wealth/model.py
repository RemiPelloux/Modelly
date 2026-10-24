"""Boltzmann wealth exchange: random pairs pass one unit of money.

``n`` agents start with ``money`` units each. Every step the agents are split into random
pairs (a uniformly random perfect matching; with an odd ``n`` one agent sits out), each
pair picks a direction at random, and the giver passes one unit to the other if it has
any. Money is conserved and never negative.

The Markov chain on configurations is symmetric: a transfer from ``i`` to ``j`` and its
reverse have the same probability, one half of the probability of the matching. Its
stationary law is therefore uniform over every way of sharing the ``M = n * money`` units
among the ``n`` agents, and one agent's wealth has the exact marginal
``P(w = k) = C(M - k + n - 2, n - 2) / C(M + n - 1, n - 1)``, which tends to the geometric
(discrete Boltzmann-Gibbs, exponential) law with mean ``money`` as ``n`` grows. Its Gini
coefficient tends to one half.

Wealth is a ``Column``, so a step is a handful of numpy operations on the whole table: no
agent is visited in a Python loop.

Validation: the time-averaged Gini coefficient and the histogram of wealth after burn-in
against ``stationary_distribution()``, the exact marginal above.

References:
    Dragulescu, A. and Yakovenko, V. M. (2000). Statistical mechanics of money. European
    Physical Journal B, 17, 723-729.
"""

from __future__ import annotations

import numpy as np

from modelly.core.agent import Agent
from modelly.core.columns import Column
from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario
from modelly.zoo.measures import gini

PAIR = 2
HALF = 0.5


class Holder(Agent):
    """An agent holding an integer amount of money."""

    wealth = Column(np.int64, default=0)


class KineticScenario(Scenario):
    """Parameters of the Boltzmann wealth exchange.

    Attributes:
        n: number of agents.
        money: units of money every agent starts with (the mean wealth).
        steps: default run length used by ``run``.
    """

    n: int = 1000
    money: int = 5
    steps: int = 1000


class KineticWealth(Model):
    """Random pairwise exchange of single units of money.

    Example:
        >>> model = KineticWealth(KineticScenario(rng=1, n=100, steps=50))
        >>> model.run()
        >>> int(model.wealth.sum())
        500
    """

    def __init__(self, scenario: KineticScenario = KineticScenario) -> None:
        """Create the agents, each with ``money`` units."""
        super().__init__(scenario=scenario)
        Holder.create_agents(self, self.scenario.n)
        self.table = self.columns[Holder]
        self.table.wealth[:] = self.scenario.money
        self.datacollector = DataCollector(model_reporters={"gini": gini_of})
        self.datacollector.collect(self)

    @property
    def wealth(self) -> np.ndarray:
        """Every agent's wealth (a live view of the column)."""
        return self.table.wealth

    def step(self) -> None:
        """One random matching; in each pair the giver passes a unit if it has one."""
        n = len(self.table)
        order = self.rng.permutation(n)
        half = n // PAIR
        first, second = order[:half], order[half : PAIR * half]
        flip = self.rng.random(half) < HALF
        giver = np.where(flip, first, second)
        taker = np.where(flip, second, first)
        wealth = self.table.wealth
        able = wealth[giver] > 0
        wealth[giver[able]] -= 1
        wealth[taker[able]] += 1
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` steps (the scenario's ``steps`` by default)."""
        self.run_for(self.scenario.steps if steps is None else steps)

    def stationary_distribution(self) -> np.ndarray:
        """Exact stationary ``P(w = k)`` for ``k = 0 .. M``, uniform configurations."""
        from scipy.special import gammaln  # noqa: PLC0415 - scipy is heavy

        n = self.scenario.n
        total = n * self.scenario.money
        k = np.arange(total + 1)
        log_ways = gammaln(total - k + n - 1) - gammaln(total - k + 1) - gammaln(n - 1)
        log_all = gammaln(total + n) - gammaln(total + 1) - gammaln(n)
        return np.exp(log_ways - log_all)

    def stationary_gini(self) -> float:
        """Gini of the exact marginal: ``E|X - Y| / (2 mean)``, ``X, Y`` independent.

        For integer variables ``E|X - Y| = 2 sum_k F(k) (1 - F(k))``.
        """
        cdf = np.cumsum(self.stationary_distribution())
        return float((cdf * (1.0 - cdf)).sum() / self.scenario.money)


def gini_of(model: KineticWealth) -> float:
    """The Gini coefficient of the agents' wealth (a model reporter)."""
    return gini(model.wealth)
