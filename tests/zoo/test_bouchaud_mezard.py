"""Bouchaud-Mezard: Gini of the inverse-gamma stationary law, rising with sigma^2 / J."""

import numpy as np
import pytest
from scipy import integrate, stats

from modelly.zoo.bouchaud_mezard.model import BouchaudMezard, BouchaudMezardScenario
from modelly.zoo.measures import gini

# sigma^2 / J = 0.5, 1, 1.5: inverse-gamma shapes 5, 3 and 7/3, all with finite variance,
# so the sample Gini has a finite-variance limit.
VOLATILITIES = (np.sqrt(0.5), 1.0, np.sqrt(1.5))
# Burn-in of 1000 steps of 0.01 is ten relaxation times 1 / J.
BURN_IN = 1000
SNAPSHOTS = 20
SPACING = 50


def inverse_gamma_gini(shape):
    """Gini of the inverse-gamma law of mean one: ``1 - int (1 - F)^2`` (Lorenz identity)."""
    law = stats.invgamma(shape, scale=shape - 1)
    area, _ = integrate.quad(lambda x: law.sf(x) ** 2, 0, np.inf, limit=200)
    return 1.0 - area


def stationary_ginis(volatility, seed):
    """The model and its Gini at spaced snapshots after burn-in."""
    model = BouchaudMezard(BouchaudMezardScenario(rng=seed, volatility=volatility))
    model.run(BURN_IN)
    ginis = []
    for _ in range(SNAPSHOTS):
        model.run(SPACING)
        ginis.append(gini(model.wealth))
    return model, np.array(ginis)


@pytest.mark.parametrize("volatility", VOLATILITIES)
@pytest.mark.parametrize("seed", [1, 2])
def test_gini_matches_inverse_gamma(volatility, seed):
    """Time-averaged Gini within three single-snapshot SDs of the analytic one.

    The mean of correlated snapshots varies less than one snapshot does; the O(dt)
    discretisation bias (about 0.001 here) is far inside the bound.
    """
    model, ginis = stationary_ginis(volatility, seed)
    expected = inverse_gamma_gini(model.stationary_shape())
    assert abs(ginis.mean() - expected) < 3 * ginis.std()


def test_gini_rises_with_inequality():
    """More noise relative to exchange: a fatter tail and a larger Gini."""
    analytic = [
        inverse_gamma_gini(1 + 2 / v**2) for v in VOLATILITIES
    ]  # J = 1 by default
    simulated = [stationary_ginis(v, 3)[1].mean() for v in VOLATILITIES]
    assert np.all(np.diff(analytic) > 0)
    assert np.all(np.diff(simulated) > 0)


def test_shape_follows_the_convention():
    """``alpha = 1 + 2 J / sigma^2``; Bouchaud and Mezard's ``mu`` uses 2 sigma^2."""
    model = BouchaudMezard(BouchaudMezardScenario(exchange=0.5, volatility=0.5))
    assert model.stationary_shape() == pytest.approx(5.0)


def test_rejects_unstable_exchange_step():
    """``exchange * dt >= 1`` would overshoot the mean."""
    with pytest.raises(ValueError, match="exchange"):
        BouchaudMezard(BouchaudMezardScenario(exchange=200.0, dt=0.01))


def test_relative_wealth_stays_positive_with_mean_one():
    """Multiplication and convex averaging keep every wealth positive; mean is one."""
    model = BouchaudMezard(BouchaudMezardScenario(rng=5, n=300, steps=300))
    model.run()
    assert model.wealth.min() > 0
    assert model.wealth.mean() == pytest.approx(1.0)


def test_same_seed_same_run():
    """Same seed, same wealth; another seed, other wealth."""

    def final(seed):
        model = BouchaudMezard(BouchaudMezardScenario(rng=seed, n=200, steps=100))
        model.run()
        return model.wealth.copy()

    assert np.array_equal(final(7), final(7))
    assert not np.array_equal(final(7), final(8))
