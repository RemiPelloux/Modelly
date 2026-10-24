"""Small importable models for the calibration tests (process workers import them by path)."""

import math

import numpy as np

from modelly import Agent, Model
from modelly.scenarios import Scenario


class SIRScenario(Scenario):
    """A closed population with one infection and one recovery rate."""

    beta: float = 0.4
    gamma: float = 0.1
    population: int = 1000
    initial: int = 10


class SIR(Model):
    """A stochastic SIR model: binomial infections and recoveries each step."""

    def __init__(self, scenario: SIRScenario = SIRScenario):  # noqa: D107
        super().__init__(scenario=scenario)
        self.susceptible = scenario.population - scenario.initial
        self.infected = scenario.initial
        self.recovered = 0

    def step(self):  # noqa: D102
        s = self.scenario
        pressure = 1 - math.exp(-s.beta * self.infected / s.population)
        infections = int(self.rng.binomial(self.susceptible, pressure))
        recoveries = int(self.rng.binomial(self.infected, 1 - math.exp(-s.gamma)))
        self.susceptible -= infections
        self.infected += infections - recoveries
        self.recovered += recoveries


class PreyPredatorScenario(Scenario):
    """Prey growth, predation and predator death rates of a stochastic Lotka-Volterra."""

    growth: float = 0.5
    predation: float = 0.01
    efficiency: float = 0.5
    death: float = 0.4
    prey0: int = 100
    predators0: int = 20


class PreyPredator(Model):
    """A stochastic Lotka-Volterra model with Poisson births and binomial losses."""

    def __init__(self, scenario: PreyPredatorScenario = PreyPredatorScenario):  # noqa: D107
        super().__init__(scenario=scenario)
        self.prey = scenario.prey0
        self.predators = scenario.predators0

    def step(self):  # noqa: D102
        s = self.scenario
        births = int(self.rng.poisson(s.growth * self.prey))
        eaten = int(
            self.rng.binomial(self.prey, 1 - math.exp(-s.predation * self.predators))
        )
        born = int(self.rng.binomial(eaten, s.efficiency))
        deaths = int(self.rng.binomial(self.predators, 1 - math.exp(-s.death)))
        self.prey += births - eaten
        self.predators += born - deaths


class Person(Agent):
    """One individual of the agent-based SIR: 0 susceptible, 1 infected, 2 recovered."""

    def __init__(self, model, state):  # noqa: D107
        super().__init__(model)
        self.state = state

    def step(self):  # noqa: D102
        model = self.model
        if self.state == 0 and self.random.random() < model.pressure:
            self.state = 1
        elif self.state == 1 and self.random.random() < model.scenario.gamma:
            self.state = 2


class AgentSIRScenario(Scenario):
    """The agent-based SIR's parameters."""

    beta: float = 0.5
    gamma: float = 0.2
    population: int = 60
    initial: int = 3


class AgentSIR(Model):
    """An agent-based SIR: uses ``shuffle_do`` and ``agent.random`` (the compiled core)."""

    def __init__(self, scenario: AgentSIRScenario = AgentSIRScenario):  # noqa: D107
        super().__init__(scenario=scenario)
        for index in range(scenario.population):
            Person(self, 1 if index < scenario.initial else 0)
        self.pressure = 0.0

    @property
    def infected(self):
        """The number of infected agents."""
        return sum(agent.state == 1 for agent in self.agents)

    def step(self):  # noqa: D102
        share = self.infected / self.scenario.population
        self.pressure = 1 - math.exp(-self.scenario.beta * share)
        self.agents.shuffle_do("step")


class Noisy(Model):
    """``value`` is ``mean`` plus normal noise of sd ``scale``, redrawn each step."""

    def __init__(self, mean=0.0, scale=1.0, rng=None):  # noqa: D107
        super().__init__(rng=rng)
        self.mean, self.scale = mean, scale
        self.value = float(self.rng.normal(mean, scale))

    def step(self):  # noqa: D102
        self.value = float(self.rng.normal(self.mean, self.scale))


def peak(series):
    """The largest value of a series (a summary statistic)."""
    return np.max(series)


def mean_and_sd(series):
    """The mean and standard deviation of a series after step 0."""
    return np.array([np.mean(series[1:]), np.std(series[1:])])


def log_counts(series):
    """``log(1 + count)`` after step 0, so large and small populations weigh alike."""
    return np.log1p(series[1:])
