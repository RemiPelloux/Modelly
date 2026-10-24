"""Hegselmann-Krause bounded-confidence opinion dynamics.

Every agent holds an opinion in ``[0, 1]``. At each step, all at once, every agent moves to
the mean opinion of the agents within ``epsilon`` of its own (itself included). Agents
further apart never influence each other, so the population splits into clusters that stop
moving after a finite number of steps; a wide bound ends in consensus.

The confidence set of an agent is a contiguous range of the sorted opinions, found with two
binary searches, and its mean comes from a running sum, so a step costs ``O(n log n)``
instead of the ``O(n^2)`` of comparing every pair. The run stops (``running`` turns
``False``) when no opinion moves by more than ``tolerance``.

Validation: consensus for ``epsilon = 0.3``, several clusters for narrow bounds, a cluster
count that falls as ``epsilon`` grows, and identical steps to the plain ``O(n^2)``
definition.

References:
    Hegselmann, R. and Krause, U. (2002). Opinion dynamics and bounded confidence: models,
    analysis and simulation. Journal of Artificial Societies and Social Simulation, 5(3).
"""

from __future__ import annotations

import numpy as np

from modelly.core.agent import Agent
from modelly.core.columns import Column
from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario
from modelly.zoo.measures import clusters

# Two opinions closer than this share of epsilon belong to the same cluster.
CLUSTER_GAP_SHARE = 0.5


class HKScenario(Scenario):
    """Parameters of the Hegselmann-Krause model.

    Attributes:
        n: number of agents.
        epsilon: confidence bound; an agent averages the opinions within it.
        tolerance: the run stops when no opinion moves by more than this.
        min_cluster_share: clusters with fewer agents than this share are not counted.
        steps: maximum run length of ``run``.
    """

    n: int = 300
    epsilon: float = 0.15
    tolerance: float = 1e-9
    min_cluster_share: float = 0.02
    steps: int = 100


class Voter(Agent):
    """An agent with an opinion in ``[0, 1]``."""

    opinion = Column(float, default=0.0)


def confidence_means(x: np.ndarray, epsilon: float) -> np.ndarray:
    """For every opinion, the mean of the opinions within ``epsilon`` of it.

    Example:
        >>> confidence_means(np.array([0.0, 0.1, 0.9]), 0.2).round(2).tolist()
        [0.05, 0.05, 0.9]
    """
    order = np.argsort(x, kind="stable")
    ranked = x[order]
    low = np.searchsorted(ranked, ranked - epsilon, side="left")
    high = np.searchsorted(ranked, ranked + epsilon, side="right")
    running = np.concatenate(([0.0], np.cumsum(ranked)))
    means = np.empty_like(x)
    means[order] = (running[high] - running[low]) / (high - low)
    return means


class HegselmannKrause(Model):
    """Every agent moves to the mean of the opinions within its confidence bound.

    Example:
        >>> model = HegselmannKrause(HKScenario(rng=1, epsilon=0.3))
        >>> model.run()
        >>> model.n_clusters(), model.running
        (1, False)
    """

    def __init__(self, scenario: HKScenario = HKScenario) -> None:
        """Create ``n`` voters with uniform random opinions."""
        super().__init__(scenario=scenario)
        Voter.create_agents(self, self.scenario.n)
        self.voters = self.columns[Voter]
        self.voters.opinion = self.rng.random(self.scenario.n)
        self.datacollector = DataCollector(
            model_reporters={"clusters": cluster_count, "spread": spread}
        )
        self.datacollector.collect(self)

    def step(self) -> None:
        """Synchronous update; stop once the opinions no longer move."""
        x = self.voters.opinion
        new = confidence_means(x, self.scenario.epsilon)
        moved = float(np.max(np.abs(new - x)))
        x[:] = new
        if moved <= self.scenario.tolerance:
            self.running = False
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Step until the opinions settle, at most ``steps`` times (scenario default)."""
        for _ in range(self.scenario.steps if steps is None else steps):
            if not self.running:
                break
            self.step()

    def n_clusters(self) -> int:
        """Opinion clusters holding at least ``min_cluster_share`` of the agents."""
        s = self.scenario
        gap = CLUSTER_GAP_SHARE * s.epsilon
        return clusters(self.voters.opinion, gap, s.min_cluster_share)


def cluster_count(model: HegselmannKrause) -> int:
    """The number of opinion clusters (a model reporter)."""
    return model.n_clusters()


def spread(model: HegselmannKrause) -> float:
    """Standard deviation of the opinions (a model reporter)."""
    return float(np.std(model.voters.opinion))
