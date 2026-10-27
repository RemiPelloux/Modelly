"""Schelling segregation on real neighbourhoods.

Schelling's model with census tracts in place of grid cells: the 41 tracts of Chittenden
County, Vermont (bundled, U.S. Census Bureau 2023 cartographic boundaries, public domain;
see ``modelly.space.geo.samples``), each with the same number of dwellings. Households of
two groups fill a share ``density`` of the dwellings at random. A household looks at the
other households of its own tract and of the tracts that touch it (queen contiguity) and
is unhappy when fewer than ``threshold`` of them belong to its group. Every step all
unhappy households leave together and move into dwellings drawn at random among those
then free, the ones they just left included. The run stops when everybody is happy.

The households are two integer columns (tract, group); neighbourhood counts for every
tract are one sparse product, ``(I + A) @ counts``, with ``A`` the tracts' adjacency.

Validation: Schelling's result, that mild preferences give strong segregation. With
``threshold = 0`` nobody is ever unhappy and nobody moves. Starting from a random
allocation, the dissimilarity index between the two groups across tracts ends far above
its value under random allocation (many standard deviations of that value, estimated
from random allocations), already for households content to be a slight minority
(``threshold = 0.45``), and it grows with the threshold.

References:
    Schelling, T. C. (1971). Dynamic models of segregation. Journal of Mathematical
    Sociology, 1(2), 143-186.

    Duncan, O. D. and Duncan, B. (1955). A methodological analysis of segregation
    indexes. American Sociological Review, 20(2), 210-217.
"""

from __future__ import annotations

import numpy as np

from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario

GROUPS = 2
HALF = 0.5  # the dissimilarity index is half the sum of share differences


class SchellingRegionsScenario(Scenario):
    """Parameters of Schelling's model on census tracts.

    Attributes:
        capacity: dwellings per tract.
        density: share of the dwellings occupied.
        group_share: share of the households in group 1.
        threshold: least share of like households in the neighbourhood for a household
            to stay.
        adjacency: a square 0/1 matrix (dense or scipy sparse) of which tracts touch;
            the queen contiguity of the bundled Chittenden County tracts when ``None``
            (needs the ``geo`` extra).
        steps: default (maximum) run length used by ``run``.
    """

    capacity: int = 20
    density: float = 0.9
    group_share: float = 0.5
    threshold: float = 0.45
    adjacency: object = None
    steps: int = 200


class SchellingRegions(Model):
    """Two groups of households relocating between neighbouring tracts.

    Example:
        >>> model = SchellingRegions(SchellingRegionsScenario(rng=1, steps=5))
        >>> model.run()
        >>> int(model.occupancy().sum()) == model.households
        True
    """

    def __init__(
        self, scenario: SchellingRegionsScenario = SchellingRegionsScenario
    ) -> None:
        """Place the households at random in the tracts' dwellings."""
        super().__init__(scenario=scenario)
        s = self.scenario
        self.neighbourhood = _neighbourhood(
            _sample_adjacency(self) if s.adjacency is None else s.adjacency
        )
        self.n = self.neighbourhood.shape[0]
        dwellings = np.repeat(np.arange(self.n), s.capacity)
        self.households = round(s.density * dwellings.size)
        self.tract = self.rng.choice(dwellings, size=self.households, replace=False)
        self.group = (self.rng.random(self.households) < s.group_share).astype(np.int8)
        self.moved = 0
        self.datacollector = DataCollector(
            model_reporters={
                "dissimilarity": lambda m: m.dissimilarity(),
                "unhappy": lambda m: int(m.unhappy().sum()),
                "moved": "moved",
            }
        )
        self.datacollector.collect(self)

    def counts(self) -> np.ndarray:
        """Households per (tract, group), shape ``(n, 2)``."""
        flat = self.tract.astype(np.int64) * GROUPS + self.group
        return np.bincount(flat, minlength=self.n * GROUPS).reshape(self.n, GROUPS)

    def occupancy(self) -> np.ndarray:
        """Households per tract."""
        return self.counts().sum(axis=1)

    def unhappy(self) -> np.ndarray:
        """Whether each household has too few like households around it."""
        around = self.neighbourhood @ self.counts()
        like = around[self.tract, self.group] - 1
        others = around[self.tract].sum(axis=1) - 1
        share = np.divide(like, others, out=np.ones(like.shape), where=others > 0)
        return share < self.scenario.threshold

    def step(self) -> None:
        """The unhappy households leave, then move into random free dwellings."""
        movers = np.flatnonzero(self.unhappy())
        self.moved = int(movers.size)
        self.running = self.moved > 0
        if self.running:
            stay = np.ones(self.households, dtype=bool)
            stay[movers] = False
            taken = np.bincount(self.tract[stay], minlength=self.n)
            free = np.repeat(np.arange(self.n), self.scenario.capacity - taken)
            self.tract[movers] = self.rng.choice(free, size=movers.size, replace=False)
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` steps (the scenario's by default), or until nobody moves."""
        for _ in range(self.scenario.steps if steps is None else steps):
            if not self.running:
                break
            self.step()

    def dissimilarity(self) -> float:
        """Duncan's index: the share of one group that would have to move to even out."""
        counts = self.counts().astype(float)
        totals = counts.sum(axis=0)
        if not totals.all():
            return 0.0
        return float(
            HALF * np.abs(counts[:, 0] / totals[0] - counts[:, 1] / totals[1]).sum()
        )


def _neighbourhood(adjacency) -> np.ndarray:
    """``I + A`` as a dense integer matrix: a tract and the tracts touching it."""
    matrix = adjacency.toarray() if hasattr(adjacency, "toarray") else adjacency
    matrix = (np.asarray(matrix) != 0).astype(np.int64)
    np.fill_diagonal(matrix, 1)
    return matrix


def _sample_adjacency(model: Model):
    """Queen contiguity of the bundled tracts (imported here: needs the geo extra)."""
    from modelly.space.geo.samples import sample_neighbourhoods  # noqa: PLC0415
    from modelly.space.geo.space import GeoSpace  # noqa: PLC0415 - geo extra

    space = GeoSpace(sample_neighbourhoods(), random=model.random)
    return space.contiguity("queen")
