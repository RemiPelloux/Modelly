"""Zero-intelligence order book: fat-tailed returns, a valid book, same seed same run."""

import numpy as np
import pytest
from scipy import stats

from modelly.zoo.order_book.model import OrderBook, OrderBookScenario

# Five standard errors of the excess kurtosis under the null of normal returns.
Z_BOUND = 5.0


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_returns_have_fat_tails(seed):
    """Excess kurtosis far above its ``sqrt(24 / n)`` standard error for normal returns."""
    model = OrderBook(OrderBookScenario(rng=seed))
    model.run()
    returns = model.returns()
    standard_error = np.sqrt(24 / returns.shape[0])
    assert stats.kurtosis(returns) > Z_BOUND * standard_error


def test_spread_is_at_least_one_tick():
    """Limit orders never cross, so the best ask stays above the best bid."""
    model = OrderBook(OrderBookScenario(rng=4, steps=500))
    model.run()
    frame = model.datacollector.get_model_vars_dataframe()
    assert frame["spread"].min() >= 1
    assert (model.bids >= 0).all() and (model.asks >= 0).all()


def test_aggressive_flow_never_empties_a_side():
    """Market orders far outpace limit orders on a one-order book: it still has quotes."""
    scenario = OrderBookScenario(
        rng=5, window=1, initial_depth=1, market_rate=5.0, limit_rate=0.1, steps=200
    )
    model = OrderBook(scenario)
    model.run()
    assert model.bids.sum() >= 1 and model.asks.sum() >= 1
    assert model.best_ask() > model.best_bid()


def test_same_seed_same_run():
    """Same seed, same mid-price path; another seed, another path."""

    def path(seed):
        model = OrderBook(OrderBookScenario(rng=seed, steps=200))
        model.run()
        return model.datacollector.get_model_vars_dataframe()["mid"]

    assert path(7).equals(path(7))
    assert not path(7).equals(path(8))
