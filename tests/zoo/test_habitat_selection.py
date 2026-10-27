"""Habitat selection on real land cover: occupancy against the Metropolis stationary law."""

import numpy as np
import pytest

pytest.importorskip("rasterio")

from modelly.zoo.habitat_selection.model import HabitatScenario, HabitatSelection

SEEDS = (1, 2, 3)
ANIMALS = 20_000
# Five multinomial standard deviations per class: no fixed seed should get near it.
Z_BOUND = 5.0
# The walk forgets its uniform start within about 100 steps (radius 8 on 120 x 120);
# a remaining bias of this size is far below one standard deviation.
BIAS = 1e-3


def z_scores(model):
    """Standardised distance of the class shares from the stationary law."""
    law = model.stationary_shares()
    sd = np.sqrt(law * (1 - law) / model.scenario.animals)
    gap = np.abs(model.shares() - law) - BIAS
    return np.divide(gap, sd, out=np.zeros_like(gap), where=sd > 0)


@pytest.mark.parametrize("seed", SEEDS)
def test_uniform_start_converges_to_the_law(seed):
    """From a uniform start on habitable cells, shares reach ``w_c n_c / sum``."""
    model = HabitatSelection(HabitatScenario(rng=seed, animals=ANIMALS))
    start = model.shares()
    model.run()
    law = model.stationary_shares()
    assert np.abs(start - law).max() > 0.2  # the start is far from the law
    assert z_scores(model).max() < Z_BOUND


def test_law_is_stationary():
    """A population started at the law stays there, at every step."""
    scenario = HabitatScenario(rng=4, animals=ANIMALS, start_at_law=True, steps=50)
    model = HabitatSelection(scenario)
    model.run()
    frame = model.datacollector.get_model_vars_dataframe()
    law = model.stationary_shares()
    sd = np.sqrt(law * (1 - law) / ANIMALS)
    worst = (frame.to_numpy() - law) / np.where(sd > 0, sd, 1.0)
    assert np.abs(worst).max() < Z_BOUND


def test_zero_weight_cells_are_never_entered():
    """Permanent water weighs nothing in the default: no animal is ever on it."""
    model = HabitatSelection(HabitatScenario(rng=5, animals=2_000, steps=100))
    model.run()
    water = model.cover[model.x, model.y] == 80
    assert not water.any()
    assert (model.cover == 80).any()


def test_equal_weights_give_area_shares():
    """With one weight for every class the law is the share of the raster's area."""
    cover = np.repeat(np.array([[1, 2, 2, 3]]), 4, axis=0)
    scenario = HabitatScenario(
        rng=6, cover=cover, preferences=((1, 1.0), (2, 1.0), (3, 1.0)), radius=1
    )
    model = HabitatSelection(scenario)
    np.testing.assert_allclose(model.stationary_shares(), [0.25, 0.5, 0.25])
    with pytest.raises(ValueError, match="positive"):
        HabitatSelection(HabitatScenario(rng=6, cover=cover, preferences=()))


def test_same_seed_same_walk():
    """Same seed, same positions; another seed, other positions."""

    def run(seed):
        model = HabitatSelection(HabitatScenario(rng=seed, animals=500, steps=20))
        model.run()
        return np.stack([model.x, model.y])

    assert np.array_equal(run(7), run(7))
    assert not np.array_equal(run(7), run(8))
