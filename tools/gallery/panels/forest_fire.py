"""Gallery panel: burnt share of the trees against tree density."""

import numpy as np

from modelly.zoo.forest_fire.model import (
    PERCOLATION_THRESHOLD,
    ForestFire,
    ForestScenario,
)

DENSITIES = np.linspace(0.4, 0.8, 17)
SEEDS = (1, 2)
SIZE = 60


def burnt(density, seed):
    """Burnt share of one fire on a SIZE x SIZE raster."""
    scenario = ForestScenario(rng=seed, density=density, width=SIZE, height=SIZE)
    model = ForestFire(scenario)
    model.run()
    return model.burnt_share()


def draw(ax):
    """Mean burnt share over two seeds, with the percolation threshold marked."""
    shares = [np.mean([burnt(d, seed) for seed in SEEDS]) for d in DENSITIES]
    ax.plot(DENSITIES, shares, marker="o")
    ax.axvline(PERCOLATION_THRESHOLD, linestyle="--", color="grey", label="$p_c$")
    ax.set_xlabel("tree density")
    ax.set_ylabel("share of trees burnt")
    ax.legend(frameon=False)
