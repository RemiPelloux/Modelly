"""Forest fire: the percolation threshold, succession mode, and same seed same run."""

import numpy as np
import pytest

from modelly.zoo.forest_fire.model import (
    PERCOLATION_THRESHOLD,
    Cover,
    ForestFire,
    ForestScenario,
)

SEEDS = (1, 2, 3)
# On a 100 x 100 lattice the transition is about L^(-3/4) ~ 0.03 wide, so densities
# 0.15 from p_c are several widths away: below, only the small clusters touching the west
# edge burn; above, the infinite cluster holds nearly every tree.
BELOW = PERCOLATION_THRESHOLD - 0.15
ABOVE = PERCOLATION_THRESHOLD + 0.15


def burn(density, seed, **changes):
    """Run one fire to the end."""
    model = ForestFire(ForestScenario(rng=seed, density=density, **changes))
    model.run()
    return model


@pytest.mark.parametrize("seed", SEEDS)
def test_below_threshold_the_fire_stays_near_the_edge(seed):
    """Below p_c the fire burns a small share of the trees and never crosses the forest."""
    model = burn(BELOW, seed)
    assert not model.running
    assert not model.spans()
    assert model.burnt_share() < 0.1


@pytest.mark.parametrize("seed", SEEDS)
def test_above_threshold_the_fire_crosses_the_forest(seed):
    """Above p_c the fire reaches the east edge and burns most trees."""
    model = burn(ABOVE, seed)
    assert model.spans()
    assert model.burnt_share() > 0.9


def test_burnt_share_rises_with_density():
    """The mean burnt share over seeds increases with tree density."""
    densities = (0.3, BELOW, PERCOLATION_THRESHOLD, ABOVE, 0.9)
    means = [np.mean([burn(d, s).burnt_share() for s in SEEDS]) for d in densities]
    assert np.all(np.diff(means) > 0)


def test_cover_raster_replaces_density():
    """A per-cell cover raster: trees only where its probability is positive."""
    cover = np.zeros((40, 30))
    cover[:20] = 1.0
    model = ForestFire(ForestScenario(rng=4, width=40, height=30, cover=cover))
    assert (model.layer[20:] == Cover.EMPTY).all()
    model.run()
    assert model.burnt_share() == 1.0  # a full forest burns completely
    assert not model.spans()


def test_succession_keeps_burning():
    """With growth and lightning the forest regrows and burns again; cells are conserved."""
    model = ForestFire(
        ForestScenario(rng=5, width=50, height=50, growth=0.02, lightning=1e-4)
    )
    model.run(150)
    assert model.running
    frame = model.datacollector.get_model_vars_dataframe()
    assert (frame.sum(axis=1) == 50 * 50).all()
    assert frame["TREE"].iloc[-1] > 0


def test_same_seed_same_run():
    """Same seed, same fire; another seed, another fire."""

    def run(seed):
        return burn(PERCOLATION_THRESHOLD, seed, width=40, height=40).state

    assert np.array_equal(run(7), run(7))
    assert not np.array_equal(run(7), run(8))
