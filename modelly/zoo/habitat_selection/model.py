"""Habitat selection on a real land-cover raster.

Animals disperse over a land-cover raster and settle where the habitat suits them. Each
land-cover class has a preference weight ``w``. Every step each animal proposes a jump to
a cell drawn uniformly from the square of side ``2 * radius + 1`` around it, and takes it
with probability ``min(1, w(new) / w(old))``; a jump off the raster is refused. The default
raster is a 120 x 120 window of ESA WorldCover 2021 at 10 m over the Intervale in
Burlington, Vermont (bundled, CC BY 4.0, © ESA WorldCover project 2021; see
``modelly.space.geo.samples``): tree cover, grassland, cropland, built-up land, the
Winooski River and wetland. The default weights describe a woodland species and are
illustrative, not fitted to any species.

Animals are independent, so their positions are two integer columns updated in one
vectorised pass per step, a few microseconds per animal.

Validation: the stationary law. The proposal is symmetric and the acceptance is the
Metropolis rule, so the walk satisfies detailed balance with ``pi(cell)`` proportional to
``w(cell)`` and, the habitable cells being connected through jumps, it converges to it.
At stationarity the share of animals on class ``c`` is ``w_c n_c / sum_k w_k n_k``, where
``n_c`` is the number of cells of class ``c``: the resource-selection-function view of
habitat use. The test starts the animals uniformly on the habitable cells and checks the
shares against this law, and checks that a population started at the law stays there.

References:
    Metropolis, N., Rosenbluth, A. W., Rosenbluth, M. N., Teller, A. H. and Teller, E.
    (1953). Equation of state calculations by fast computing machines. Journal of
    Chemical Physics, 21(6), 1087-1092.

    Manly, B. F. J., McDonald, L. L., Thomas, D. L., McDonald, T. L. and Erickson, W. P.
    (2002). Resource Selection by Animals, 2nd ed. Kluwer.

    Zanaga, D. et al. (2022). ESA WorldCover 10 m 2021 v200. Zenodo,
    doi:10.5281/zenodo.7254221.
"""

from __future__ import annotations

import numpy as np

from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario

# WorldCover class value to preference weight: an illustrative woodland species.
WOODLAND = (
    (10, 1.0),  # tree cover
    (20, 0.8),  # shrubland
    (30, 0.4),  # grassland
    (40, 0.2),  # cropland
    (50, 0.02),  # built-up
    (60, 0.05),  # bare or sparse vegetation
    (80, 0.0),  # permanent water
    (90, 0.5),  # herbaceous wetland
)


class HabitatScenario(Scenario):
    """Parameters of the habitat-selection model.

    Attributes:
        animals: number of animals.
        radius: the largest jump along each axis, in cells.
        preferences: ``(class value, weight)`` pairs; classes not listed weigh 0.
        cover: the land-cover classes, shape ``(width, height)`` (a ``RasterLayer``'s
            ``values``); the bundled WorldCover window when ``None`` (needs ``geo``).
        start_at_law: start the animals at the stationary law instead of uniformly on
            the habitable cells.
        steps: default run length used by ``run``.
    """

    animals: int = 5_000
    radius: int = 8
    preferences: tuple = WOODLAND
    cover: object = None
    start_at_law: bool = False
    steps: int = 400


class HabitatSelection(Model):
    """Metropolis dispersal over a land-cover raster, weighted by habitat preference.

    Example:
        >>> model = HabitatSelection(HabitatScenario(rng=1, steps=10))
        >>> model.run()
        >>> round(float(model.shares().sum()), 6)
        1.0
    """

    def __init__(self, scenario: HabitatScenario = HabitatScenario) -> None:
        """Weigh every cell and place the animals."""
        super().__init__(scenario=scenario)
        s = self.scenario
        self.cover = np.asarray(_sample_cover() if s.cover is None else s.cover)
        self.classes = np.unique(self.cover)
        weights = dict(s.preferences)
        self.weight = np.vectorize(lambda c: weights.get(int(c), 0.0))(self.cover)
        self.weight = self.weight.astype(float)
        if not (self.weight > 0).any():
            raise ValueError("No cell has a positive preference weight.")
        flat = self.weight.ravel()
        chance = flat if s.start_at_law else (flat > 0).astype(float)
        cells = self.rng.choice(flat.size, size=s.animals, p=chance / chance.sum())
        self.x, self.y = np.unravel_index(cells, self.cover.shape)
        self.datacollector = DataCollector(
            model_reporters={f"class_{int(c)}": _share_of(int(c)) for c in self.classes}
        )
        self.datacollector.collect(self)

    def step(self) -> None:
        """Every animal proposes a jump and takes it by the Metropolis rule."""
        s = self.scenario
        width, height = self.cover.shape
        jump = self.rng.integers(-s.radius, s.radius + 1, size=(2, s.animals))
        to_x, to_y = self.x + jump[0], self.y + jump[1]
        inside = (to_x >= 0) & (to_x < width) & (to_y >= 0) & (to_y < height)
        to_x, to_y = np.where(inside, to_x, self.x), np.where(inside, to_y, self.y)
        ratio = self.weight[to_x, to_y] / self.weight[self.x, self.y]
        accept = inside & (self.rng.random(s.animals) < ratio)
        self.x = np.where(accept, to_x, self.x)
        self.y = np.where(accept, to_y, self.y)
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` steps (the scenario's ``steps`` by default)."""
        self.run_for(self.scenario.steps if steps is None else steps)

    def shares(self) -> np.ndarray:
        """Share of the animals on each class of ``classes``."""
        here = self.cover[self.x, self.y]
        return np.array([(here == c).mean() for c in self.classes])

    def stationary_shares(self) -> np.ndarray:
        """Share of each class of ``classes`` at the stationary law, ``w_c n_c / sum``."""
        mass = np.array([self.weight[self.cover == c].sum() for c in self.classes])
        return mass / mass.sum()


def _sample_cover() -> np.ndarray:
    """The bundled WorldCover window (imported here: needs the geo extra)."""
    from modelly.space.geo.samples import sample_landcover  # noqa: PLC0415 - geo extra

    return sample_landcover().values


def _share_of(value: int):
    """A model reporter: the share of the animals on land-cover class ``value``."""

    def share(model: HabitatSelection) -> float:
        return float((model.cover[model.x, model.y] == value).mean())

    return share
