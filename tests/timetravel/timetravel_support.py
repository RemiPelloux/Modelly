"""Shared models and fingerprints for the time travel tests."""

from modelly import Model
from modelly.examples import BoidFlockers, BoltzmannWealth, Schelling, WolfSheep
from modelly.examples.advanced.wolf_sheep.model import WolfSheepScenario
from modelly.examples.basic.boid_flockers.model import BoidsScenario
from modelly.examples.basic.boltzmann_wealth_model.model import BoltzmannScenario
from modelly.examples.basic.schelling.model import SchellingScenario
from modelly.scenarios import Scenario
from modelly.timetravel import model_state

SEED = 42

EXAMPLES = {
    "wolf_sheep": lambda seed=SEED: WolfSheep(WolfSheepScenario(rng=seed)),
    "boltzmann": lambda seed=SEED: BoltzmannWealth(BoltzmannScenario(rng=seed)),
    "schelling": lambda seed=SEED: Schelling(SchellingScenario(rng=seed)),
    "boids": lambda seed=SEED: BoidFlockers(BoidsScenario(rng=seed)),
}


def _collected(model):
    """The DataCollector history, if the model has a collector."""
    collector = getattr(model, "datacollector", None)
    if collector is None:
        return None
    return collector.model_vars, collector._agent_records


def fingerprint(model):
    """Everything a bit-identical rewind and replay must reproduce."""
    return {
        "time": model.time,
        "random": model.random.getstate(),
        "rng": model.rng.bit_generator.state,
        "collected": _collected(model),
        "state": model_state(model),
        "events": sorted(
            (e.time, int(e.priority))
            for e in model._event_list._events
            if not e.CANCELED
        ),
    }


class DriftScenario(Scenario):
    """A scenario whose ``rate`` is read in every step."""

    rate: float = 1.0


class Drift(Model):
    """A model that reads its scenario during the run, not only at creation."""

    def __init__(self, scenario=DriftScenario):
        """Start at level zero."""
        super().__init__(scenario=scenario)
        self.level = 0.0

    def step(self):
        """Drift by ``rate`` times a random draw."""
        self.level += self.scenario.rate * self.random.random()
