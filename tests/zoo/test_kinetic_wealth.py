"""Boltzmann wealth exchange: the exact stationary law, conservation, same seed same run."""

import numpy as np
import pytest

from modelly.zoo.kinetic_wealth.model import KineticScenario, KineticWealth
from modelly.zoo.measures import gini

# Burn-in: one agent's wealth is a random walk of variance about 1/2 per step and the
# stationary variance is money * (money + 1) = 30, so 500 steps are many relaxation times.
BURN_IN = 500
SNAPSHOTS = 20
SPACING = 25
SEEDS = (1, 2, 3)


def snapshots(seed):
    """Wealth of every agent at ``SNAPSHOTS`` spaced times after burn-in."""
    model = KineticWealth(KineticScenario(rng=seed))
    model.run(BURN_IN)
    taken = []
    for _ in range(SNAPSHOTS):
        model.run(SPACING)
        taken.append(model.wealth.copy())
    return model, np.array(taken)


def single_snapshot_tv(p, n):
    """Expected total-variation distance of one histogram of ``n`` independent draws.

    ``E|p_hat - p| = sqrt(2 / pi) * sd`` per bin (normal approximation), halved for TV.
    Pooling correlated snapshots can only shrink it, so it bounds the pooled histogram.
    """
    return float(np.sqrt(2 / np.pi) * np.sqrt(p * (1 - p) / n).sum() / 2)


@pytest.mark.parametrize("seed", SEEDS)
def test_stationary_gini(seed):
    """The time-averaged Gini is within three single-snapshot SDs of the exact law's."""
    model, taken = snapshots(seed)
    ginis = np.array([gini(w) for w in taken])
    # The mean of correlated snapshots varies less than one snapshot does.
    assert abs(ginis.mean() - model.stationary_gini()) < 3 * ginis.std()
    assert model.stationary_gini() == pytest.approx(0.5, abs=0.05)


@pytest.mark.parametrize("seed", SEEDS)
def test_stationary_histogram(seed):
    """The pooled wealth histogram is closer to the exact marginal than one snapshot."""
    model, taken = snapshots(seed)
    p = model.stationary_distribution()
    empirical = np.bincount(taken.ravel(), minlength=p.shape[0]) / taken.size
    distance = 0.5 * np.abs(empirical - p).sum()
    assert distance < single_snapshot_tv(p, model.scenario.n)


def test_exact_marginal_is_a_distribution_with_the_right_mean():
    """``P(w = k)`` sums to one and has mean ``money``."""
    model = KineticWealth(KineticScenario(rng=0, n=50, money=3))
    p = model.stationary_distribution()
    assert p.sum() == pytest.approx(1.0)
    assert (np.arange(p.shape[0]) * p).sum() == pytest.approx(3.0)


def test_money_is_conserved_and_never_negative():
    """Odd population (one agent sits out each step), total fixed, nobody in debt."""
    model = KineticWealth(KineticScenario(rng=4, n=101, money=1, steps=200))
    model.run()
    assert int(model.wealth.sum()) == 101
    assert model.wealth.min() >= 0


def test_starts_equal():
    """Before any exchange everybody holds the same: Gini zero."""
    model = KineticWealth(KineticScenario(rng=0))
    assert model.datacollector.get_model_vars_dataframe()["gini"].iloc[0] == 0.0


def test_same_seed_same_run():
    """Same seed, same wealth; another seed, other wealth."""

    def final(seed):
        model = KineticWealth(KineticScenario(rng=seed, n=200, steps=100))
        model.run()
        return model.wealth.copy()

    assert np.array_equal(final(7), final(7))
    assert not np.array_equal(final(7), final(8))
