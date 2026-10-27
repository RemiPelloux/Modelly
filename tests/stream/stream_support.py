"""A small epidemic and its observations, shared by the assimilation tests."""

import hashlib
import math

import numpy as np

from modelly import Agent, Model
from modelly.scenarios import Scenario
from modelly.stream import (
    Ensemble,
    ObservationOperator,
    ParticleFilter,
    ReplaySource,
)

DAYS = 20
NOISE = 2.0
REPLICATES = 12
TRUTH_SEED = 1
ENSEMBLE_SEED = 2
NOISE_SEED = 99
TRUE_BETA = 0.5
PRIOR_LOW, PRIOR_HIGH = 0.2, 0.8


class TownScenario(Scenario):
    """A town of ``people``, ``seeded`` of them infected on day 0."""

    people: int = 200
    seeded: int = 5
    beta: float = 0.3
    recovery: float = 0.15


class Person(Agent):
    """Susceptible, infected or recovered."""

    def __init__(self, model, infected):
        """A person, infected or not."""
        super().__init__(model)
        self.infected = infected
        self.recovered = False


class Town(Model):
    """A stochastic SIR epidemic whose contact rate is the attribute ``beta``."""

    def __init__(self, scenario):
        """Build the town from ``scenario``."""
        super().__init__(scenario=scenario)
        self.beta = scenario.beta
        self.new_cases = 0
        for i in range(scenario.people):
            Person(self, infected=i < scenario.seeded)

    def step(self):
        """Infections and recoveries of one day."""
        people = list(self.agents)
        chance = 1 - math.exp(-self.beta * self.prevalence / len(people))
        self.new_cases = 0
        for person in people:
            if person.infected:
                if self.random.random() < self.scenario.recovery:
                    person.infected, person.recovered = False, True
            elif not person.recovered and self.random.random() < chance:
                person.infected = True
                self.new_cases += 1

    @property
    def prevalence(self):
        """How many are infected now."""
        return sum(person.infected for person in self.agents)


def cases():
    """The observed quantity: new cases of the day."""
    return ObservationOperator(cases=_new_cases)


def _new_cases(model):
    """New cases of the day, read from a model."""
    return model.new_cases


def _uniform_prior(rng):
    """A contact rate drawn uniformly over the prior range."""
    return rng.uniform(PRIOR_LOW, PRIOR_HIGH)


PRIOR = {"beta": _uniform_prior}


def observations(days=DAYS):
    """Noisy daily case counts of a truth run with ``TRUE_BETA``."""
    truth = Town(TownScenario(rng=TRUTH_SEED, beta=TRUE_BETA))
    noise = np.random.default_rng(NOISE_SEED)
    records = []
    for day in range(1, days + 1):
        truth.step()
        records.append({"time": day, "cases": truth.new_cases + noise.normal(0, NOISE)})
    return records


def ensemble(seed=ENSEMBLE_SEED, n=REPLICATES):
    """An ensemble of towns whose contact rates come from the prior."""
    return Ensemble(Town, TownScenario(rng=seed), n, prior=PRIOR)


def filtered(seed=ENSEMBLE_SEED, threshold=1.0):
    """A particle filter run over every observation."""
    pf = ParticleFilter(ensemble(seed), cases(), sd=NOISE, threshold=threshold)
    pf.run(ReplaySource(observations()))
    return pf


def fingerprint(pf):
    """A digest of everything a reproducible filter run must repeat, bit for bit."""
    digest = hashlib.sha256()
    digest.update(pf.weights.tobytes())
    digest.update(pf.history.to_numpy(dtype=float).tobytes())
    for model in pf.ensemble:
        state = (model.beta, model.new_cases, model.prevalence, model.random.getstate())
        digest.update(repr(state).encode())
        digest.update(repr(model.rng.bit_generator.state).encode())
    return digest.hexdigest()
