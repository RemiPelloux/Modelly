"""Schelling on real census tracts: no moves without preference, strong segregation."""

import numpy as np
import pytest

pytest.importorskip("geopandas")

from modelly.zoo.schelling_regions.model import (
    SchellingRegions,
    SchellingRegionsScenario,
)

SEEDS = (1, 2, 3)
BASELINE_SEEDS = range(100, 130)
# Segregation must end this many standard deviations above random allocation.
Z_BOUND = 5.0


@pytest.fixture(scope="module")
def adjacency():
    """Queen contiguity of the bundled Chittenden County tracts, computed once."""
    return SchellingRegions(SchellingRegionsScenario(rng=0)).neighbourhood


def run(adjacency, seed, threshold):
    """A finished run of the model at ``threshold``."""
    scenario = SchellingRegionsScenario(
        rng=seed, threshold=threshold, adjacency=adjacency
    )
    model = SchellingRegions(scenario)
    model.run()
    return model


def test_tracts_and_their_neighbours(adjacency):
    """41 tracts, each its own neighbour, the adjacency symmetric and connected."""
    assert adjacency.shape == (41, 41)
    assert (np.diag(adjacency) == 1).all()
    assert (adjacency == adjacency.T).all()
    from scipy.sparse.csgraph import connected_components  # noqa: PLC0415

    assert connected_components(adjacency, directed=False)[0] == 1


def test_no_preference_no_moves(adjacency):
    """With ``threshold = 0`` nobody is unhappy and the allocation never changes."""
    model = SchellingRegions(
        SchellingRegionsScenario(rng=1, threshold=0.0, adjacency=adjacency)
    )
    start = model.tract.copy()
    model.run()
    assert model.moved == 0
    assert np.array_equal(model.tract, start)


@pytest.mark.parametrize("seed", SEEDS)
def test_mild_preferences_segregate(adjacency, seed):
    """Content to be a slight minority, households still end strongly segregated."""
    random = [
        SchellingRegions(
            SchellingRegionsScenario(rng=s, adjacency=adjacency)
        ).dissimilarity()
        for s in BASELINE_SEEDS
    ]
    bound = np.mean(random) + Z_BOUND * np.std(random)
    model = run(adjacency, seed, 0.45)
    assert model.dissimilarity() > bound
    assert model.dissimilarity() > 2 * np.mean(random)


def test_segregation_grows_with_the_threshold(adjacency):
    """Mean dissimilarity over seeds rises from no preference to a majority preference."""
    means = [
        np.mean([run(adjacency, seed, t).dissimilarity() for seed in SEEDS])
        for t in (0.0, 0.3, 0.5)
    ]
    assert means[0] <= means[1] + 0.02 < means[2]
    assert means[2] > 0.9


def test_households_and_dwellings_are_conserved(adjacency):
    """Moves never create or lose households, nor overfill a tract."""
    model = run(adjacency, 4, 0.5)
    s = model.scenario
    assert model.occupancy().sum() == model.households
    assert (model.occupancy() <= s.capacity).all()
    assert model.counts().sum(axis=0).tolist() == np.bincount(model.group).tolist()


def test_same_seed_same_moves(adjacency):
    """Same seed, same history; another seed, another one."""

    def history(seed):
        return run(adjacency, seed, 0.45).datacollector.get_model_vars_dataframe()

    assert history(5).equals(history(5))
    assert not history(5).equals(history(6))
