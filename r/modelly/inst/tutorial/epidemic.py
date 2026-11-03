"""The SIR model of the calibration tutorial (docs/calibration.md), for the R and Julia packages."""

import math

from modelly import Model
from modelly.data.collector import DataCollector
from modelly.scenarios import Scenario


class EpidemicScenario(Scenario):
    """Rates per day, the population and the initial cases."""

    beta: float = 0.4  # infection rate
    gamma: float = 0.1  # recovery rate
    population: int = 1000
    initial: int = 10


class Epidemic(Model):
    """A stochastic SIR model: binomial infections and recoveries each day."""

    def __init__(self, scenario: EpidemicScenario = EpidemicScenario):
        """Everybody susceptible but the initial cases."""
        super().__init__(scenario=scenario)
        self.susceptible = scenario.population - scenario.initial
        self.infected = scenario.initial
        self.recovered = 0
        self.datacollector = DataCollector(
            model_reporters={
                name: name for name in ("susceptible", "infected", "recovered")
            }
        )
        self.datacollector.collect(self)

    def step(self):
        """One day of infections and recoveries."""
        s = self.scenario
        pressure = 1 - math.exp(-s.beta * self.infected / s.population)
        infections = int(self.rng.binomial(self.susceptible, pressure))
        recoveries = int(self.rng.binomial(self.infected, 1 - math.exp(-s.gamma)))
        self.susceptible -= infections
        self.infected += infections - recoveries
        self.recovered += recoveries
        self.datacollector.collect(self)
