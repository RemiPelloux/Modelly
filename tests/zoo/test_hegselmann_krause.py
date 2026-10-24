"""Hegselmann-Krause model: consensus versus clusters, and the O(n log n) step."""

from itertools import pairwise

import numpy as np
import pytest

from modelly.zoo.hegselmann_krause.model import (
    HegselmannKrause,
    HKScenario,
    confidence_means,
)

SEEDS = (1, 2, 3)
# Running sums reorder the additions of the plain mean: rounding differences only.
FLOAT_TOLERANCE = 1e-12


def naive_means(x, epsilon):
    """The definition: for each agent, the mean over every agent within epsilon."""
    close = np.abs(x[:, None] - x[None, :]) <= epsilon
    return (close * x[None, :]).sum(axis=1) / close.sum(axis=1)


def settled(epsilon, seed):
    """The model run to rest for one bound and seed."""
    model = HegselmannKrause(HKScenario(rng=seed, epsilon=epsilon))
    model.run()
    return model


@pytest.mark.parametrize("seed", SEEDS)
def test_wide_bound_reaches_consensus(seed):
    """Above the consensus threshold (about 0.2 for a few hundred agents) all agree."""
    model = settled(0.3, seed)
    assert not model.running
    assert model.n_clusters() == 1


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("epsilon", [0.05, 0.1])
def test_narrow_bound_leaves_several_clusters(epsilon, seed):
    """Narrow bounds freeze into several clusters, at most about 1 / (2 epsilon)."""
    clusters = settled(epsilon, seed).n_clusters()
    assert 2 < clusters <= int(1 / (2 * epsilon))


def test_cluster_count_falls_as_the_bound_grows():
    """Mean cluster count over the seeds is non-increasing in epsilon."""
    bounds = (0.05, 0.1, 0.2, 0.3)
    means = [np.mean([settled(eps, s).n_clusters() for s in SEEDS]) for eps in bounds]
    assert all(a >= b for a, b in pairwise(means))
    assert means[-1] == 1


def test_step_matches_the_quadratic_definition():
    """Sorted ranges and running sums give the same means as comparing every pair."""
    rng = np.random.default_rng(8)
    x = rng.random(200)
    for _ in range(5):
        fast = confidence_means(x, 0.12)
        assert np.allclose(fast, naive_means(x, 0.12), rtol=0, atol=FLOAT_TOLERANCE)
        x = fast


def test_zero_bound_never_moves():
    """With epsilon = 0 every agent only sees itself and the run stops at once."""
    model = HegselmannKrause(HKScenario(rng=4, epsilon=0.0))
    start = model.voters.opinion.copy()
    model.run()
    assert not model.running
    assert model.time == 1
    assert np.allclose(model.voters.opinion, start, rtol=0, atol=FLOAT_TOLERANCE)


def test_same_seed_same_run():
    """Same seed, same opinions; another seed, other opinions."""
    assert np.array_equal(
        settled(0.1, 6).voters.opinion, settled(0.1, 6).voters.opinion
    )
    assert not np.array_equal(
        settled(0.1, 6).voters.opinion, settled(0.1, 7).voters.opinion
    )
