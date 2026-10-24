"""Small importable models for the experiment tests (workers import them by path)."""

from modelly import Agent, Model
from modelly.scenarios import Scenario


class WalkScenario(Scenario):
    """Parameters of the random walk."""

    n: int = 10
    drift: float = 0.0
    policy: str = "none"
    fail: bool = False


class Walker(Agent):
    """An agent taking normal steps around a drift."""

    def __init__(self, model):  # noqa: D107
        super().__init__(model)
        self.position = 0.0

    def step(self):  # noqa: D102
        self.position += self.model.scenario.drift + self.model.rng.normal()


class Walk(Model):
    """Walkers whose mean position is the output; ``fail`` raises after step 1."""

    def __init__(self, scenario: WalkScenario = WalkScenario):  # noqa: D107
        super().__init__(scenario=scenario)
        Walker.create_agents(self, scenario.n)

    def step(self):  # noqa: D102
        if self.scenario.fail and self.time >= 1:
            raise RuntimeError("asked to fail")
        self.agents.shuffle_do("step")

    def mean(self):
        """The mean position."""
        return sum(a.position for a in self.agents) / len(self.agents)

    @property
    def spread(self):
        """The largest position minus the smallest."""
        positions = [a.position for a in self.agents]
        return max(positions) - min(positions)


def first_position(model):
    """The position of the first agent (an output given as a function)."""
    return next(iter(model.agents)).position


class Plain(Model):
    """A model with no Scenario class: parameters go to its constructor.

    It stops itself (``running = False``) after ``stop_at`` steps when given.
    """

    def __init__(self, rate=1.0, stop_at=None, rng=None):  # noqa: D107
        super().__init__(rng=rng)
        self.rate = rate
        self.stop_at = stop_at
        self.value = 0.0

    def step(self):  # noqa: D102
        self.value += self.rate * self.rng.random()
        if self.stop_at is not None and self.time >= self.stop_at:
            self.running = False


ATTEMPTS = {}


def flaky_value(model):
    """An output that raises on the first call for each rate, then reads ``value``."""
    key = model.rate
    ATTEMPTS[key] = ATTEMPTS.get(key, 0) + 1
    if ATTEMPTS[key] == 1:
        raise RuntimeError("first attempt fails")
    return model.value


def not_a_scalar(model):
    """An output of the wrong kind."""
    return [model.value]
