"""Virus on a random network, written for Mesa 2.3.

One agent per node of an Erdos-Renyi graph. Every step, synchronously: each
susceptible node catches the virus from each infected neighbour independently
with probability ``beta``; each infected node recovers with probability
``gamma`` and is then resistant with probability ``resistance``, susceptible
otherwise.
"""

from __future__ import annotations

import mesa
import networkx as nx
from mesa.space import NetworkGrid

S, I, R = 0, 1, 2


class Node(mesa.Agent):
    """A node; ``next_state`` keeps the update synchronous."""

    def __init__(self, unique_id, model, state):
        super().__init__(unique_id, model)
        self.state = state
        self.next_state = state

    def expose(self):
        model = self.model
        if self.state == S:
            for other in model.grid.get_neighbors(self.pos):
                if other.state == I and self.random.random() < model.beta:
                    self.next_state = I
                    break
        elif self.state == I and self.random.random() < model.gamma:
            self.next_state = R if self.random.random() < model.resistance else S

    def advance(self):
        self.state = self.next_state


class Contagion(mesa.Model):
    """The graph and its nodes."""

    def __init__(self, n, avg_degree, beta, gamma, resistance, outbreak, seed):
        super().__init__(seed=seed)
        self.beta, self.gamma, self.resistance = beta, gamma, resistance
        graph = nx.fast_gnp_random_graph(n, avg_degree / (n - 1), seed=seed)
        self.grid = NetworkGrid(graph)
        infected = set(self.random.sample(range(n), max(1, int(outbreak * n))))
        for node_id in graph.nodes:
            self.grid.place_agent(
                Node(node_id, self, I if node_id in infected else S), node_id
            )
        self.infected_history = []

    def step(self):
        agents = self.agents
        agents.do("expose")
        agents.do("advance")
        self.infected_history.append(sum(1 for a in agents if a.state == I))


# Mesa 2.3 seeds ``model.random`` in ``Model.__new__`` from the keyword ``seed``;
# a positional seed leaves the model unseeded.
def build(seed, n, avg_degree, beta, gamma, resistance, outbreak):
    """Build the model."""
    return Contagion(n, avg_degree, beta, gamma, resistance, outbreak, seed=seed)


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
