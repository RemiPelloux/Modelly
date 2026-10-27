"""SIR on a contact network, written to be split across processes.

One person per node of a small-world network (Watts and Strogatz: a ring
lattice of ``degree`` neighbours with each edge rewired with probability
``rewiring``). Every step has two phases:

1. ``infect``: a susceptible person with ``k`` infected neighbours is infected
   with probability ``1 - (1 - beta) ** k``; an infected person recovers with
   probability ``gamma``; both decided from the states at the start of the
   phase, reading neighbours one hop away (``radius=1``);
2. ``advance``: everyone takes the state decided in ``infect``.

People never move, so a split by ``partition.graph`` only exchanges ghosts:
the neighbours across a cut edge. Each worker creates only the people of its
part (``owns``); a person's stream key is its node's index.
"""

from __future__ import annotations

from modelly.core.model import Model
from modelly.distributed.building import owns
from modelly.distributed.contract import Partitionable, Phase
from modelly.distributed.reduce import Max, Sum
from modelly.scenarios.scenario import Scenario
from modelly.space.cells.agents import FixedAgent
from modelly.space.network import Network

SUSCEPTIBLE, INFECTED, RECOVERED = 0, 1, 2
SEED_BOUND = 2**31  # networkx takes an int seed


class NetworkScenario(Scenario):
    """Parameters of the network SIR model.

    Attributes:
        people: nodes of the network, one person each.
        degree: neighbours of each node in the ring lattice before rewiring.
        rewiring: chance that an edge is rewired to a random node.
        infected: people infected at the start (the first nodes).
        beta: chance of infection per infected neighbour and step.
        gamma: chance of recovery per step.
    """

    people: int = 1_000
    degree: int = 6
    rewiring: float = 0.05
    infected: int = 5
    beta: float = 0.1
    gamma: float = 0.1


class Person(FixedAgent):
    """One person on a node: ``state`` and the state decided next."""

    def __init__(self, model: NetworkSIR, cell, state: int, key: int) -> None:
        """Person ``key`` (its node's place in the node order), of ``state``, on ``cell``."""
        super().__init__(model)
        self.key = key
        self.cell = cell
        self.state = state
        self.next_state = state
        self.infected_days = 0

    def stream_key(self) -> int:
        """The person's node index, whoever builds it."""
        return self.key

    def infect(self) -> None:
        """Decide the next state from the neighbours' states at the start of the phase."""
        scenario = self.model.scenario
        if self.state == SUSCEPTIBLE:
            cells = self.cell.neighborhood.cells
            k = sum(other.state == INFECTED for cell in cells for other in cell.agents)
            if k and self.random.random() < 1.0 - (1.0 - scenario.beta) ** k:
                self.next_state = INFECTED
        elif self.state == INFECTED:
            self.infected_days += 1
            if self.random.random() < scenario.gamma:
                self.next_state = RECOVERED

    def advance(self) -> None:
        """Take the state decided in ``infect``."""
        self.state = self.next_state


def infected(model: Model) -> int:
    """People infected."""
    return sum(1 for agent in model.agents if agent.state == INFECTED)


def recovered(model: Model) -> int:
    """People recovered."""
    return sum(1 for agent in model.agents if agent.state == RECOVERED)


def longest_infection(model: Model) -> int:
    """The most steps any person has been infected."""
    return max((agent.infected_days for agent in model.agents), default=0)


class NetworkSIR(Model):
    """An epidemic spreading along the edges of a small-world network."""

    agent_streams = True
    partitionable = Partitionable(
        space="network",
        phases=(Phase("infect", radius=1), Phase("advance")),
        reporters={
            "I": Sum(infected),
            "R": Sum(recovered),
            "longest": Max(longest_infection),
        },
    )

    def __init__(self, scenario: NetworkScenario = NetworkScenario) -> None:
        """Draw the network and put one person on each node."""
        import networkx as nx  # noqa: PLC0415 - networkx is an optional dependency

        super().__init__(scenario=scenario)
        s = self.scenario
        seed = int(self.rng.integers(SEED_BOUND))
        graph = nx.watts_strogatz_graph(s.people, s.degree, s.rewiring, seed=seed)
        self.network = Network(graph, capacity=1, random=self.random)
        for key, cell in enumerate(self.network.all_cells):
            if owns(self, cell.coordinate):
                state = INFECTED if key < s.infected else SUSCEPTIBLE
                Person(self, cell, state, key)

    def step(self) -> None:
        """The two phases, in order."""
        self.partitionable.step(self)
