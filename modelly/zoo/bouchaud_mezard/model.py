"""Bouchaud-Mezard wealth condensation: random returns plus exchange.

Each agent's wealth follows, in the mean-field version of the model,
``dW_i = J (mean(W) - W_i) dt + sigma W_i dB_i`` (Ito): an independent random return on
what it holds, of variance ``sigma^2`` per unit time, and an exchange that pulls it toward
the mean at rate ``J``. A step of length ``dt`` applies the multiplicative part exactly,
``W_i <- W_i exp(sigma sqrt(dt) xi_i - sigma^2 dt / 2)`` with ``xi_i`` standard normal
(mean preserving), then the exchange ``W_i <- W_i + J dt (mean(W) - W_i)``, then divides by
the mean, so ``wealth`` is relative wealth ``w = W / mean(W)``.

The Fokker-Planck equation of ``w`` has the stationary density
``P(w) ~ exp(-(alpha - 1) / w) / w^(1 + alpha)``, an inverse-gamma law with shape
``alpha = 1 + 2 J / sigma^2`` and scale ``alpha - 1`` (mean one): a Pareto tail of
exponent ``alpha``. Bouchaud and Mezard write the noise variance as ``2 sigma^2``, hence
their ``mu = 1 + J / sigma^2``; with the convention here it is ``1 + 2 J / sigma^2``. The
larger ``sigma^2 / J``, the fatter the tail and the more unequal the wealth.

Validation: the Gini coefficient of the simulated stationary wealth against the Gini of
the inverse-gamma law (``stationary_shape()``), and its increase with ``sigma^2 / J``.

References:
    Bouchaud, J.-P. and Mezard, M. (2000). Wealth condensation in a simple model of
    economy. Physica A, 282, 536-545.
"""

from __future__ import annotations

import numpy as np

from modelly.core.agent import Agent
from modelly.core.columns import Column
from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario
from modelly.zoo.measures import gini

HALF = 0.5


class Saver(Agent):
    """An agent holding a (relative) amount of wealth."""

    wealth = Column(float, default=1.0)


class BouchaudMezardScenario(Scenario):
    """Parameters of the Bouchaud-Mezard model.

    Attributes:
        n: number of agents.
        exchange: exchange rate ``J`` per unit time.
        volatility: ``sigma``, the standard deviation of returns per unit time.
        dt: length of a step; ``exchange * dt`` must be below one.
        steps: default run length used by ``run``.
    """

    n: int = 2000
    exchange: float = 1.0
    volatility: float = 1.0
    dt: float = 0.01
    steps: int = 2000


class BouchaudMezard(Model):
    """Multiplicative noise and mean-field exchange of wealth.

    Example:
        >>> model = BouchaudMezard(BouchaudMezardScenario(rng=1, n=100, steps=10))
        >>> model.run()
        >>> round(float(model.wealth.mean()), 6)
        1.0
    """

    def __init__(
        self, scenario: BouchaudMezardScenario = BouchaudMezardScenario
    ) -> None:
        """Create the agents, all with relative wealth one."""
        super().__init__(scenario=scenario)
        s = self.scenario
        if not 0 < s.exchange * s.dt < 1:
            raise ValueError("exchange * dt must be between 0 and 1.")
        Saver.create_agents(self, s.n)
        self.table = self.columns[Saver]
        self.datacollector = DataCollector(model_reporters={"gini": gini_of})
        self.datacollector.collect(self)

    @property
    def wealth(self) -> np.ndarray:
        """Every agent's wealth relative to the mean (a live view of the column)."""
        return self.table.wealth

    def step(self) -> None:
        """Random returns, then exchange toward the mean, then renormalise."""
        s = self.scenario
        w = self.table.wealth
        shocks = self.rng.standard_normal(w.shape[0])
        drift = HALF * s.volatility**2 * s.dt
        w *= np.exp(s.volatility * np.sqrt(s.dt) * shocks - drift)
        w += s.exchange * s.dt * (w.mean() - w)
        w /= w.mean()
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` steps (the scenario's ``steps`` by default)."""
        self.run_for(self.scenario.steps if steps is None else steps)

    def stationary_shape(self) -> float:
        """Shape ``alpha = 1 + 2 J / sigma^2`` of the stationary inverse-gamma law."""
        s = self.scenario
        return 1.0 + 2.0 * s.exchange / s.volatility**2


def gini_of(model: BouchaudMezard) -> float:
    """The Gini coefficient of the agents' wealth (a model reporter)."""
    return gini(model.wealth)
