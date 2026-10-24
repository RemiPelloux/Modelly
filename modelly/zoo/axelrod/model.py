"""Axelrod's model of the dissemination of culture.

Every site of a square grid holds a culture: ``features`` features, each taking one of
``traits`` values. At each event a random site and a random neighbour interact with
probability equal to their cultural overlap (the share of features on which they agree);
when they interact, the site copies one of the features on which they differ. Similar
neighbours become more similar, and neighbours with nothing in common never interact, so
the grid freezes into regions of identical culture. Few traits per feature end in a single
culture; many traits leave many regions (the transition studied by Castellano, Marsili and
Vespignani).

The sites are the rows of a ``CellIndex`` over a von Neumann grid, the cultures one
``(n_sites, features)`` integer array. Events stay sequential, as in the original, but a
step pre-draws ``events_per_step`` sites, neighbours (``CellIndex.random_neighbor``) and
uniforms in three numpy calls and runs the events on plain lists. After each step the
model checks, over every bond at once, whether a pair with partial overlap is left; when
none is, the culture map is frozen and ``running`` turns ``False``. Cultural regions are
the connected components of the bonds with full overlap.

Validation: with five features on a 10 x 10 grid, two traits end in one region for most
seeds and thirty traits in many; the mean number of regions grows with the traits.

References:
    Axelrod, R. (1997). The dissemination of culture: a model with local convergence and
    global polarization. Journal of Conflict Resolution, 41(2), 203-226.

    Castellano, C., Marsili, M. and Vespignani, A. (2000). Nonequilibrium phase transition
    in a model for social influence. Physical Review Letters, 85(16), 3536-3539.
"""

from __future__ import annotations

import numpy as np

from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario
from modelly.space.cells.index import CellIndex
from modelly.space.grid.grids import OrthogonalVonNeumannGrid


class AxelrodScenario(Scenario):
    """Parameters of Axelrod's culture model.

    Attributes:
        width: grid width (sites).
        height: grid height (sites).
        features: cultural features per site.
        traits: values each feature can take.
        events_per_step: interactions attempted per step.
        steps: maximum run length of ``run``; it stops earlier once the map is frozen.
    """

    width: int = 10
    height: int = 10
    features: int = 5
    traits: int = 10
    events_per_step: int = 2_000
    steps: int = 500


class Axelrod(Model):
    """Sites copy cultural traits from similar neighbours until no bond is active.

    Example:
        >>> model = Axelrod(AxelrodScenario(rng=1, traits=2))
        >>> model.run()
        >>> model.running, model.n_regions()
        (False, 1)
    """

    def __init__(self, scenario: AxelrodScenario = AxelrodScenario) -> None:
        """Draw a uniformly random culture for every site."""
        super().__init__(scenario=scenario)
        s = self.scenario
        self.grid = OrthogonalVonNeumannGrid((s.width, s.height), random=self.random)
        self.index = CellIndex(self.grid)
        shape = (self.index.n, s.features)
        self.culture = self.rng.integers(0, s.traits, size=shape)
        upper = self.index.adjacency.tocoo()
        keep = upper.row < upper.col  # each bond once
        self.bonds = np.stack((upper.row[keep], upper.col[keep]), axis=1)
        self.datacollector = DataCollector(
            model_reporters={"regions": region_count, "active_bonds": active_bonds}
        )
        self.datacollector.collect(self)

    def step(self) -> None:
        """Run ``events_per_step`` events, then stop if no bond is active."""
        s = self.scenario
        sites = self.rng.integers(0, self.index.n, size=s.events_per_step)
        partners = self.index.random_neighbor(sites, self.rng)
        uniforms = self.rng.random((s.events_per_step, 2)).tolist()
        culture = self.culture.tolist()
        for site, partner, (accept, pick) in zip(
            sites.tolist(), partners.tolist(), uniforms
        ):
            interact(culture[site], culture[partner], accept, pick)
        self.culture[:] = culture
        if active_bonds(self) == 0:
            self.running = False
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Step until the map is frozen, at most ``steps`` times (scenario default)."""
        for _ in range(self.scenario.steps if steps is None else steps):
            if not self.running:
                break
            self.step()

    def overlaps(self) -> np.ndarray:
        """Number of shared features across every bond."""
        left, right = self.bonds[:, 0], self.bonds[:, 1]
        return (self.culture[left] == self.culture[right]).sum(axis=1)

    def n_regions(self) -> int:
        """Connected regions of identical culture."""
        from scipy.sparse import coo_matrix  # noqa: PLC0415 - scipy is heavy
        from scipy.sparse.csgraph import connected_components  # noqa: PLC0415

        same = self.bonds[self.overlaps() == self.scenario.features]
        n = self.index.n
        ones = np.ones(same.shape[0])
        graph = coo_matrix((ones, (same[:, 0], same[:, 1])), shape=(n, n))
        return int(connected_components(graph, directed=False)[0])


def interact(site: list[int], partner: list[int], accept: float, pick: float) -> None:
    """One event: with probability overlap / F, ``site`` copies one differing feature."""
    differ = [k for k, (a, b) in enumerate(zip(site, partner)) if a != b]
    if not differ or len(differ) == len(site):
        return
    if accept < 1.0 - len(differ) / len(site):
        feature = differ[int(pick * len(differ))]
        site[feature] = partner[feature]


def region_count(model: Axelrod) -> int:
    """The number of cultural regions (a model reporter)."""
    return model.n_regions()


def active_bonds(model: Axelrod) -> int:
    """Bonds whose sites share some but not all features (a model reporter)."""
    overlap = model.overlaps()
    return int(((overlap > 0) & (overlap < model.scenario.features)).sum())
