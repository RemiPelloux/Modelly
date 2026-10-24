"""Virus on a random network, written for Modelly.

Same model as ``mesa_model.py``. The infected-neighbour count of every node is
one sparse matrix-vector product (``CellIndex.neighbor_sum``); infection,
recovery and resistance are three Bernoulli vectors.
"""

from __future__ import annotations

import networkx as nx
import numpy as np

from modelly import Column, Model
from modelly.space import CellIndex, FixedAgent, Network

S, I, R = 0, 1, 2


class Node(FixedAgent):
    """A node; its state and cell row live in the column table."""

    state = Column(np.int8, default=S)
    row = Column(np.intp, default=-1)

    def __init__(self, model, cell, state):
        super().__init__(model)
        self.cell = cell
        self.row = cell.index
        self.state = state


class Contagion(Model):
    """The graph, its nodes and the vectorised step."""

    def __init__(self, n, avg_degree, beta, gamma, resistance, outbreak, rng):
        super().__init__(rng=rng)
        self.beta, self.gamma, self.resistance = beta, gamma, resistance
        graph = nx.fast_gnp_random_graph(n, avg_degree / (n - 1), seed=rng)
        self.network = Network(graph, random=self.random)
        self.index = CellIndex(self.network)
        infected = set(self.random.sample(range(n), max(1, int(outbreak * n))))
        for node_id, cell in zip(graph.nodes, self.index.cells):
            Node(self, cell, I if node_id in infected else S)
        self.infected_history = []

    def step(self):
        table = self.columns[Node]
        state, rows = table.state, table.row
        infected = state == I
        exposure = self.index.neighbor_sum(self.index.counts(rows, infected))[rows]
        catches = (state == S) & table.draw(1.0 - (1.0 - self.beta) ** exposure)
        recovers = infected & table.draw(self.gamma)
        resistant = recovers & table.draw(self.resistance)
        state[catches] = I
        state[recovers] = S
        state[resistant] = R
        self.infected_history.append(int((state == I).sum()))


def build(seed, n, avg_degree, beta, gamma, resistance, outbreak):
    """Build the model."""
    return Contagion(n, avg_degree, beta, gamma, resistance, outbreak, seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    model.run_for(steps)
    history = model.infected_history
    state = model.columns[Node].state
    peak = max(history)
    return {
        "population": int(state.shape[0]),
        "stats": {
            "final_S": int((state == S).sum()),
            "final_I": int((state == I).sum()),
            "final_R": int((state == R).sum()),
            "peak_I": peak,
            "peak_step": history.index(peak) + 1,
            "mean_I": sum(history) / len(history),
        },
    }
