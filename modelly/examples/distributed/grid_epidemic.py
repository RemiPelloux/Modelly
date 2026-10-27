"""Synchronous SIR on a torus grid, written to be split across processes.

The grid epidemic of the benchmark playbooks (``benchmarks/playbooks/grid_epidemic``)
under the contract of ``modelly.distributed``. Every step has three phases:

1. ``move``: each person steps to a random Moore neighbour cell (``moves=True``);
2. ``expose``: a susceptible person with ``k`` infected people in its own cell
   and the eight around it is infected with probability ``1 - (1 - beta) ** k``,
   from the states at the start of the phase (``radius=1``); an infected person
   counts its days and is due to recover after ``recovery`` of them;
3. ``advance``: everyone takes the state decided in ``expose``.

Every draw is the person's own (``agent_streams = True``), people hold plain
data, and ``expose`` reads other people only within one cell, so a run split
into grid blocks gives the same numbers as one process. Each person's stream key
is its index in the creation order, so a split build creates only the people of
its own block (``owns``) and still gives everyone the stream of one process.
"""

from __future__ import annotations

from modelly.core.model import Model
from modelly.distributed.building import owns
from modelly.distributed.contract import Partitionable, Phase
from modelly.distributed.reduce import Sum
from modelly.scenarios.scenario import Scenario
from modelly.space.cells.agents import CellAgent
from modelly.space.grid.grids import OrthogonalMooreGrid

SUSCEPTIBLE, INFECTED, RECOVERED = 0, 1, 2


class EpidemicScenario(Scenario):
    """Parameters of the grid epidemic.

    Attributes:
        width: cells along the first axis of the torus.
        height: cells along the second axis.
        people: number of people.
        infected: people infected at the start (the first ones created).
        beta: chance of infection per infected neighbour and step.
        recovery: steps from infection to recovery.
    """

    width: int = 40
    height: int = 40
    people: int = 2_000
    infected: int = 20
    beta: float = 0.08
    recovery: int = 8


class Person(CellAgent):
    """One person: ``state``, ``days`` infected and the state decided next."""

    def __init__(self, model: GridEpidemic, cell, state: int, key: int) -> None:
        """Person number ``key``, of ``state``, in ``cell``."""
        super().__init__(model)
        self.key = key
        self.cell = cell
        self.state = state
        self.next_state = state
        self.days = 0

    def stream_key(self) -> int:
        """The person's number in the creation order, whoever builds it."""
        return self.key

    def move(self) -> None:
        """Step to a random Moore neighbour cell, drawn from the person's own stream."""
        self.cell = self.random.choice(self.cell.neighborhood.cells)

    def expose(self) -> None:
        """Decide the next state from the states around, at the start of the phase."""
        scenario = self.model.scenario
        if self.state == SUSCEPTIBLE:
            around = [self.cell, *self.cell.neighborhood.cells]
            k = sum(other.state == INFECTED for cell in around for other in cell.agents)
            if k and self.random.random() < 1.0 - (1.0 - scenario.beta) ** k:
                self.next_state = INFECTED
        elif self.state == INFECTED:
            self.days += 1
            if self.days >= scenario.recovery:
                self.next_state = RECOVERED

    def advance(self) -> None:
        """Take the state decided in ``expose``."""
        self.state = self.next_state


def susceptible(model: Model) -> int:
    """People susceptible."""
    return sum(1 for agent in model.agents if agent.state == SUSCEPTIBLE)


def infected(model: Model) -> int:
    """People infected."""
    return sum(1 for agent in model.agents if agent.state == INFECTED)


def recovered(model: Model) -> int:
    """People recovered."""
    return sum(1 for agent in model.agents if agent.state == RECOVERED)


class GridEpidemic(Model):
    """People walking on a torus grid and infecting the people around them."""

    agent_streams = True
    partitionable = Partitionable(
        space="grid",
        phases=(
            Phase("move", moves=True),
            Phase("expose", radius=1),
            Phase("advance"),
        ),
        reporters={"S": Sum(susceptible), "I": Sum(infected), "R": Sum(recovered)},
    )

    def __init__(self, scenario: EpidemicScenario = EpidemicScenario) -> None:
        """Create the torus and place the people at random cells (this block's only)."""
        super().__init__(scenario=scenario)
        s = self.scenario
        self.grid = OrthogonalMooreGrid(
            (s.width, s.height), torus=True, random=self.random
        )
        cells = list(self.grid.all_cells)
        picks = self.rng.integers(0, len(cells), size=s.people).tolist()
        for key, pick in enumerate(picks):
            cell = cells[pick]
            if owns(self, cell.coordinate):
                state = INFECTED if key < s.infected else SUSCEPTIBLE
                Person(self, cell, state, key)

    def step(self) -> None:
        """The three phases, in order."""
        self.partitionable.step(self)
