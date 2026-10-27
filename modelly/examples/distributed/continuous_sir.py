"""SIR among walkers in a continuous torus, written to be split across processes.

People take a step of fixed length in a random direction every step
(``moves=True``); a susceptible person with ``k`` infected people within
``reach`` of it is infected with probability ``1 - (1 - beta) ** k`` and an
infected person recovers after ``recovery`` steps (``radius=reach``); then
everyone takes the state decided. A ``partition.kd`` split cuts the square
into boxes of nearly equal population; ghosts are the people within ``reach``
of a neighbouring box.
"""

from __future__ import annotations

import math

from modelly.core.model import Model
from modelly.distributed.contract import Partitionable, Phase
from modelly.distributed.reduce import Sum
from modelly.scenarios.scenario import Scenario
from modelly.space.continuous.agents import ContinuousSpaceAgent
from modelly.space.continuous.space import ContinuousSpace

SUSCEPTIBLE, INFECTED, RECOVERED = 0, 1, 2
REACH = 1.0  # infection distance; the expose phase's radius


class WalkerScenario(Scenario):
    """Parameters of the walkers' epidemic.

    Attributes:
        side: length of the torus side.
        people: number of people.
        infected: people infected at the start.
        speed: length of a step.
        beta: chance of infection per infected person within reach and step.
        recovery: steps from infection to recovery.
    """

    side: float = 30.0
    people: int = 600
    infected: int = 10
    speed: float = 0.5
    beta: float = 0.1
    recovery: int = 8


class Walker(ContinuousSpaceAgent):
    """A person in the plane: ``state``, ``days`` infected, the state decided next."""

    def __init__(self, model: ContinuousSIR, state: int) -> None:
        """A person of ``state`` in the model's space."""
        super().__init__(model.space, model)
        self.state = state
        self.next_state = state
        self.days = 0

    def move(self) -> None:
        """Take one step in a direction drawn from the person's own stream."""
        angle = self.random.random() * 2.0 * math.pi
        speed = self.model.scenario.speed
        step = (speed * math.cos(angle), speed * math.sin(angle))
        self.position = self.position + step

    def expose(self) -> None:
        """Decide the next state from the people within reach, at the phase start."""
        scenario = self.model.scenario
        if self.state == SUSCEPTIBLE:
            others, _ = self.get_neighbors_in_radius(REACH)
            k = sum(other.state == INFECTED for other in others)
            if k and self.random.random() < 1.0 - (1.0 - scenario.beta) ** k:
                self.next_state = INFECTED
        elif self.state == INFECTED:
            self.days += 1
            if self.days >= scenario.recovery:
                self.next_state = RECOVERED

    def advance(self) -> None:
        """Take the state decided in ``expose``."""
        self.state = self.next_state


def infected(model: Model) -> int:
    """People infected."""
    return sum(1 for agent in model.agents if agent.state == INFECTED)


def recovered(model: Model) -> int:
    """People recovered."""
    return sum(1 for agent in model.agents if agent.state == RECOVERED)


class ContinuousSIR(Model):
    """Walkers infecting the people near them in a continuous torus."""

    agent_streams = True
    partitionable = Partitionable(
        space="space",
        phases=(
            Phase("move", moves=True),
            Phase("expose", radius=REACH),
            Phase("advance"),
        ),
        reporters={"I": Sum(infected), "R": Sum(recovered)},
    )

    def __init__(self, scenario: WalkerScenario = WalkerScenario) -> None:
        """Place the people uniformly at random in the torus."""
        super().__init__(scenario=scenario)
        s = self.scenario
        bounds = [[0.0, s.side], [0.0, s.side]]
        self.space = ContinuousSpace(bounds, torus=True, random=self.random)
        positions = self.rng.random((s.people, 2)) * s.side
        for i, position in enumerate(positions):
            walker = Walker(self, INFECTED if i < s.infected else SUSCEPTIBLE)
            walker.position = position

    def step(self) -> None:
        """The three phases, in order."""
        self.partitionable.step(self)
