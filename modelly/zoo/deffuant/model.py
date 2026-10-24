"""Deffuant bounded-confidence opinion dynamics.

Every agent holds an opinion in ``[0, 1]``. Two agents who meet compromise only when their
opinions differ by less than the confidence bound ``epsilon``: each moves a fraction ``mu``
of the way towards the other. A wide bound ends in consensus; a narrow one freezes the
population into several opinion clusters, about ``floor(1 / (2 epsilon))`` of them for
opinions drawn uniformly.

The original model picks one random pair per time step. Here one step is a sweep: the
agents are put into a uniformly random perfect matching (a permutation cut into
consecutive pairs) and every pair interacts at once, from the start-of-step opinions. The
pairs are disjoint, so the updates do not interfere, and every agent meets exactly one
uniformly random partner per step; a step is about ``n / 2`` events of the original
dynamics, with the same kind of absorbing states (clusters more than ``epsilon`` apart).
Opinions are a ``Column``, so the sweep is three numpy operations.

Validation: one cluster for ``epsilon = 0.4``, several for ``epsilon = 0.1`` (around
``1 / (2 epsilon) = 5``), and a cluster count that does not grow as ``epsilon`` grows.

References:
    Deffuant, G., Neau, D., Amblard, F. and Weisbuch, G. (2000). Mixing beliefs among
    interacting agents. Advances in Complex Systems, 3, 87-98.
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
PAIR = 2


class DeffuantScenario(Scenario):
    """Parameters of the Deffuant model.

    Attributes:
        n: number of agents.
        epsilon: confidence bound; agents further apart than this ignore each other.
        mu: convergence parameter, the share of the difference each partner moves.
        min_cluster_share: clusters with fewer agents than this share are not counted.
        steps: default run length of ``run`` (sweeps, each about ``n / 2`` meetings).
    """

    n: int = 500
    epsilon: float = 0.2
    mu: float = 0.5
    min_cluster_share: float = 0.02
    steps: int = 300


class Voter(Agent):
    """An agent with an opinion in ``[0, 1]``."""

    opinion = Column(float, default=0.0)


class Deffuant(Model):
    """Random pairs compromise when their opinions are within ``epsilon``.

    Example:
        >>> model = Deffuant(DeffuantScenario(rng=1, epsilon=0.4, steps=200))
        >>> model.run()
        >>> model.n_clusters()
        1
    """

    def __init__(self, scenario: DeffuantScenario = DeffuantScenario) -> None:
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
        """One sweep: a random perfect matching, every close pair compromises."""
        s = self.scenario
        x = self.voters.opinion
        order = self.rng.permutation(x.shape[0])
        pairs = order[: order.shape[0] // PAIR * PAIR].reshape(-1, PAIR)
        left, right = pairs[:, 0], pairs[:, 1]
        difference = x[right] - x[left]
        close = np.abs(difference) < s.epsilon
        shift = s.mu * difference * close
        x[left] += shift
        x[right] -= shift
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` sweeps (the scenario's ``steps`` by default)."""
        self.run_for(self.scenario.steps if steps is None else steps)

    def n_clusters(self) -> int:
        """Opinion clusters holding at least ``min_cluster_share`` of the agents."""
        s = self.scenario
        gap = CLUSTER_GAP_SHARE * s.epsilon
        return clusters(self.voters.opinion, gap, s.min_cluster_share)


def cluster_count(model: Deffuant) -> int:
    """The number of opinion clusters (a model reporter)."""
    return model.n_clusters()


def spread(model: Deffuant) -> float:
    """Standard deviation of the opinions (a model reporter)."""
    return float(np.std(model.voters.opinion))
