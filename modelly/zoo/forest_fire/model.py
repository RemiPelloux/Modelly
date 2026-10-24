"""Forest fire and succession on a raster.

A raster of cells, each empty, a tree, burning or burnt. At the start every cell holds a tree
with probability ``density`` (or with its own probability, from a ``cover`` raster such as the
values of a ``modelly.space.geo.RasterLayer``), and the trees of the west edge are set alight.
Every step a tree next to a burning cell (von Neumann neighbourhood) catches fire and a
burning cell burns out. With ``growth > 0`` empty and burnt cells grow a tree with that
probability per step and with ``lightning > 0`` a tree is struck with that probability per
step: the Drossel-Schwabl forest-fire model of succession and disturbance.

The state is one integer per cell, a property layer of the grid (``model.layer``, shaped
like the grid); the spread is one sparse product per step, ``CellIndex.neighbor_sum``, over
the grid's adjacency.

Validation: without growth and lightning the fire burns exactly the clusters of trees that
touch the west edge, so the model is site percolation on the square lattice. The share of
trees burnt jumps, and the fire starts to reach the east edge, at the percolation threshold
``p_c = 0.592746`` (Newman and Ziff 2000): it stays small below and covers most trees above.

References:
    Drossel, B. and Schwabl, F. (1992). Self-organized critical forest-fire model.
    Physical Review Letters, 69(11), 1629-1632.

    Newman, M. E. J. and Ziff, R. M. (2000). Efficient Monte Carlo algorithm and
    high-precision results for percolation. Physical Review Letters, 85(19), 4104-4107.

    Stauffer, D. and Aharony, A. (1994). Introduction to Percolation Theory, 2nd ed.
    Taylor and Francis.
"""

from __future__ import annotations

from enum import IntEnum
from functools import partial

import numpy as np

from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario
from modelly.space.cells.index import CellIndex
from modelly.space.grid.grids import OrthogonalVonNeumannGrid

# Site-percolation threshold of the square lattice (Newman and Ziff 2000).
PERCOLATION_THRESHOLD = 0.592746
WEST = 0


class Cover(IntEnum):
    """Cell states."""

    EMPTY = 0
    TREE = 1
    BURNING = 2
    BURNT = 3


class ForestScenario(Scenario):
    """Parameters of the forest-fire model.

    Attributes:
        width: cells from west to east.
        height: cells from south to north.
        density: probability that a cell starts with a tree.
        cover: optional per-cell tree probability, shape ``(width, height)`` (a raster's
            values); replaces ``density`` when given.
        growth: probability per step that an empty or burnt cell grows a tree.
        lightning: probability per step that a tree is struck and catches fire.
        steps: default run length used by ``run``.
    """

    width: int = 100
    height: int = 100
    density: float = 0.6
    cover: object = None
    growth: float = 0.0
    lightning: float = 0.0
    steps: int = 2_000


class ForestFire(Model):
    """Fire spreading through a tree raster, with optional regrowth and lightning.

    Example:
        >>> model = ForestFire(ForestScenario(rng=1, width=30, height=30))
        >>> model.run()
        >>> 0.0 <= model.burnt_share() <= 1.0
        True
    """

    def __init__(self, scenario: ForestScenario = ForestScenario) -> None:
        """Plant the trees and ignite the west edge."""
        super().__init__(scenario=scenario)
        s = self.scenario
        self.grid = OrthogonalVonNeumannGrid((s.width, s.height), random=self.random)
        self.index = CellIndex(self.grid)
        chance = np.full((s.width, s.height), s.density) if s.cover is None else s.cover
        chance = np.asarray(chance, dtype=float).ravel()
        trees = self.rng.random(self.index.n) < chance
        self.state = np.where(trees, Cover.TREE, Cover.EMPTY).astype(np.int8)
        self.layer = self.index.to_layer(self.state)
        self.layer[WEST][self.layer[WEST] == Cover.TREE] = Cover.BURNING
        self.initial_trees = int(trees.sum())
        self.datacollector = DataCollector(
            model_reporters={c.name: partial(count_of, cover=c) for c in Cover}
        )
        self.datacollector.collect(self)

    def step(self) -> None:
        """Spread, burn out, then (in succession mode) strike and regrow."""
        s = self.scenario
        state = self.state
        burning = state == Cover.BURNING
        exposed = self.index.neighbor_sum(burning.astype(np.int32)) > 0
        catch = (state == Cover.TREE) & exposed
        if s.lightning > 0:
            catch |= (state == Cover.TREE) & (
                self.rng.random(state.shape) < s.lightning
            )
        state[burning] = Cover.BURNT
        state[catch] = Cover.BURNING
        if s.growth > 0:
            bare = (state == Cover.EMPTY) | (state == Cover.BURNT)
            state[bare & (self.rng.random(state.shape) < s.growth)] = Cover.TREE
        self.running = bool(burning.any() or s.growth > 0 or s.lightning > 0)
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` steps (the scenario's by default), or until the fire is out."""
        for _ in range(self.scenario.steps if steps is None else steps):
            if not self.running:
                break
            self.step()

    def burnt_share(self) -> float:
        """Share of the initial trees that have burnt or are burning."""
        fire = np.isin(self.state, (Cover.BURNING, Cover.BURNT)).sum()
        return float(fire / max(self.initial_trees, 1))

    def spans(self) -> bool:
        """Whether the fire has reached the east edge."""
        east = self.layer[-1]
        return bool(np.isin(east, (Cover.BURNING, Cover.BURNT)).any())


def count_of(model: ForestFire, cover: Cover) -> int:
    """The number of cells in state ``cover`` (a model reporter)."""
    return int((model.state == cover).sum())
