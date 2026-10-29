"""Virus on a random network, migrated from Mesa 3.5 to Modelly by the codemod alone (see ../README.md).

Same model as ``mesa_model.py``. One ``FixedAgent`` per cell of a
``modelly.discrete_space.Network`` built on an Erdos-Renyi graph. Every step,
synchronously: each susceptible node catches the virus from each infected
neighbour independently with probability ``beta``; each infected node recovers
with probability ``gamma`` and is then resistant with probability
``resistance``, susceptible otherwise.
"""

from __future__ import annotations

import networkx as nx

from modelly import Model
from modelly.space import FixedAgent, Network

S, I, R = 0, 1, 2


class Node(FixedAgent):
    """A node; ``next_state`` keeps the update synchronous."""

    def __init__(self, model, cell, state):
        super().__init__(model)
        self.cell = cell
        self.state = state
        self.next_state = state

    def expose(self):
        model = self.model
        if self.state == S:
            for other in self.cell.neighborhood.agents:
                if other.state == I and self.random.random() < model.beta:
                    self.next_state = I
                    break
        elif self.state == I and self.random.random() < model.gamma:
            self.next_state = R if self.random.random() < model.resistance else S

    def advance(self):
        self.state = self.next_state


class Contagion(Model):
    """The network and its nodes."""

    def __init__(self, n, avg_degree, beta, gamma, resistance, outbreak, rng):
        super().__init__(rng=rng)
        self.beta, self.gamma, self.resistance = beta, gamma, resistance
        graph = nx.fast_gnp_random_graph(n, avg_degree / (n - 1), seed=rng)
        # ``layout=None``: a purely topological network; the default spring
        # layout only serves visualisation and is costly on large graphs.
        self.grid = Network(graph, capacity=1, random=self.random, layout=None)
        infected = set(self.random.sample(range(n), max(1, int(outbreak * n))))
        nodes = list(graph.nodes)
        cells = [self.grid[node_id] for node_id in nodes]
        states = [I if node_id in infected else S for node_id in nodes]
        Node.create_agents(self, n, cells, states)
        self.infected_history = []

    def step(self):
        self.agents.do("expose")
        self.agents.do("advance")
        self.infected_history.append(sum(1 for a in self.agents if a.state == I))


def build(seed, n, avg_degree, beta, gamma, resistance, outbreak):
    """Build the model."""
    return Contagion(n, avg_degree, beta, gamma, resistance, outbreak, rng=seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    for _ in range(steps):
        model.step()
    history = model.infected_history
    states = [a.state for a in model.agents]
    peak = max(history)
    return {
        "population": len(states),
        "stats": {
            "final_S": states.count(S),
            "final_I": states.count(I),
            "final_R": states.count(R),
            "peak_I": peak,
            "peak_step": history.index(peak) + 1,
            "mean_I": sum(history) / len(history),
        },
    }
