"""Bass diffusion of an innovation (rooftop solar, heat pumps) on a network.

Every household either has adopted the innovation or not. In each step of length ``dt``
(in years) a household that has not adopted does so with probability
``(innovation + imitation * share) * dt``: ``innovation`` is the pull of advertising and
``imitation`` the pull of the households it knows, ``share`` being the share of its
neighbours that have adopted. With ``mixing="well-mixed"`` the share is that of the whole
population, as in Bass's original model; with ``mixing="network"`` it is over the household's
neighbours in a random network of mean degree ``degree`` (a ``MultilayerNetwork`` with one
layer), so the infection pressure is one sparse product per step.

Households are ``Household`` agents whose ``adopted`` flag is a ``Column``; the whole
population adopts in one ``ColumnTable.draw``.

Validation: in the well-mixed limit the expected cumulative adoption follows the Bass
equation ``dF/dt = (innovation + imitation * F) * (1 - F)``, whose solution is
``F(t) = (1 - exp(-(p + q) t)) / (1 + (q / p) exp(-(p + q) t))`` with ``p = innovation``
and ``q = imitation``; ``bass_curve`` evaluates it. On a dense random network the curve
stays close to it; on a sparse one adoption is slower, because non-adopters cluster
together and see fewer adopters than the population average.

References:
    Bass, F. M. (1969). A new product growth for model consumer durables. Management
    Science, 15(5), 215-227.
"""

from __future__ import annotations

import numpy as np

from modelly.core.agent import Agent
from modelly.core.columns import Column
from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario
from modelly.space.networks.multilayer import MultilayerNetwork

WELL_MIXED = "well-mixed"
NETWORK = "network"
LAYER = "acquaintance"


class BassScenario(Scenario):
    """Parameters of the Bass diffusion model.

    Attributes:
        households: number of households.
        innovation: Bass ``p``, adoption rate per year from outside influence.
        imitation: Bass ``q``, adoption rate per year when every neighbour has adopted.
        dt: length of a step, in years.
        mixing: ``"well-mixed"`` (share over everybody) or ``"network"``.
        degree: mean number of neighbours in the random network.
        steps: default run length used by ``run``.
    """

    households: int = 5000
    innovation: float = 0.03
    imitation: float = 0.38
    dt: float = 0.1
    mixing: str = WELL_MIXED
    degree: float = 10.0
    steps: int = 200


class Household(Agent):
    """A household; ``adopted`` is 1 once it has adopted."""

    adopted = Column(np.int8)


class BassDiffusion(Model):
    """Households adopting from advertising and from their neighbours.

    Example:
        >>> model = BassDiffusion(BassScenario(rng=1, steps=50))
        >>> model.run()
        >>> 0 < model.adoption < 1
        True
    """

    def __init__(self, scenario: BassScenario = BassScenario) -> None:
        """Create the households and, for ``mixing="network"``, their network."""
        super().__init__(scenario=scenario)
        s = self.scenario
        if s.mixing not in (WELL_MIXED, NETWORK):
            raise ValueError(
                f"mixing is {WELL_MIXED!r} or {NETWORK!r}, not {s.mixing!r}"
            )
        Household.create_agents(self, s.households)
        self.households = self.columns[Household]
        self.network = self.random_network() if s.mixing == NETWORK else None
        self.datacollector = DataCollector(
            model_reporters={"time": "time_in_years", "adoption": "adoption"}
        )
        self.datacollector.collect(self)

    def random_network(self) -> MultilayerNetwork:
        """An Erdos-Renyi-like graph: ``households * degree / 2`` random distinct pairs."""
        s = self.scenario
        n = s.households
        pairs = self.rng.integers(0, n, size=(round(n * s.degree / 2), 2))
        pairs = pairs[pairs[:, 0] != pairs[:, 1]]
        network = MultilayerNetwork(n, [LAYER])
        network.add_edges(pairs.tolist(), LAYER)
        return network

    def neighbour_share(self) -> np.ndarray | float:
        """Share of adopters among each household's neighbours (or everybody's)."""
        adopted = self.households.adopted.astype(float)
        if self.network is None:
            return float(adopted.mean())
        adjacency = self.network.adjacency()
        degree = np.asarray(adjacency.sum(axis=1)).ravel()
        pressure = adjacency @ adopted
        return np.divide(
            pressure, degree, out=np.zeros_like(pressure), where=degree > 0
        )

    def step(self) -> None:
        """Every non-adopter adopts with probability ``(p + q * share) * dt``."""
        s = self.scenario
        table = self.households
        hazard = (s.innovation + s.imitation * self.neighbour_share()) * s.dt
        new = table.draw(np.minimum(hazard, 1.0)) & (table.adopted == 0)
        table.adopted[new] = 1
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` steps (the scenario's ``steps`` by default)."""
        self.run_for(self.scenario.steps if steps is None else steps)

    @property
    def adoption(self) -> float:
        """Share of households that have adopted."""
        return float(self.households.adopted.mean())

    @property
    def time_in_years(self) -> float:
        """Elapsed time in years: steps times ``dt``."""
        return float(self.time * self.scenario.dt)


def bass_curve(t: np.ndarray, innovation: float, imitation: float) -> np.ndarray:
    """The Bass solution ``F(t)``: cumulative share adopted at time ``t``, from ``F(0) = 0``.

    Example:
        >>> float(bass_curve(np.array([0.0]), 0.03, 0.38)[0])
        0.0
    """
    decay = np.exp(-(innovation + imitation) * np.asarray(t, dtype=float))
    return (1.0 - decay) / (1.0 + (imitation / innovation) * decay)
