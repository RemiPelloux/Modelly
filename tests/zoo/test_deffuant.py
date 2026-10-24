"""Deffuant model: consensus versus clusters as the confidence bound changes."""

from itertools import pairwise

import numpy as np
import pytest

from modelly.zoo.deffuant.model import Deffuant, DeffuantScenario

SEEDS = (1, 2, 3)


def clusters_at(epsilon, seed):
    """Clusters left after the default run for one bound and seed."""
    model = Deffuant(DeffuantScenario(rng=seed, epsilon=epsilon))
    model.run()
    return model.n_clusters()


@pytest.mark.parametrize("seed", SEEDS)
def test_wide_bound_reaches_consensus(seed):
    """Deffuant et al.: for epsilon above about 0.25 the population agrees."""
    assert clusters_at(0.4, seed) == 1


@pytest.mark.parametrize("seed", SEEDS)
def test_narrow_bound_leaves_about_one_over_two_epsilon_clusters(seed):
    """The published rule of thumb is floor(1 / (2 epsilon)) = 5 major clusters at 0.1.

    The count fluctuates by one or two between runs (clusters merge or a small one sits
    between two big ones), so the band is the rule plus or minus two.
    """
    expected = int(1 / (2 * 0.1))
    assert expected - 2 <= clusters_at(0.1, seed) <= expected + 2


def test_cluster_count_falls_as_the_bound_grows():
    """Mean cluster count over the seeds is non-increasing in epsilon."""
    bounds = (0.05, 0.1, 0.2, 0.4)
    means = [np.mean([clusters_at(eps, seed) for seed in SEEDS]) for eps in bounds]
    assert all(a >= b for a, b in pairwise(means))
    assert means[0] > means[-1]


def test_no_interaction_without_confidence():
    """With epsilon = 0 nobody is ever close enough: the opinions never move."""
    model = Deffuant(DeffuantScenario(rng=4, epsilon=0.0, steps=20))
    start = model.voters.opinion.copy()
    model.run()
    assert np.array_equal(model.voters.opinion, start)


def test_mean_opinion_is_conserved():
    """Each compromise moves both partners by the same amount in opposite directions."""
    model = Deffuant(DeffuantScenario(rng=5, steps=50))
    start = model.voters.opinion.mean()
    model.run()
    assert model.voters.opinion.mean() == pytest.approx(start, abs=1e-12)


def test_same_seed_same_run():
    """Same seed, same opinions; another seed, other opinions."""

    def opinions(seed):
        model = Deffuant(DeffuantScenario(rng=seed, steps=30))
        model.run()
        return model.voters.opinion.copy()

    assert np.array_equal(opinions(6), opinions(6))
    assert not np.array_equal(opinions(6), opinions(7))
