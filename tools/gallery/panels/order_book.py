"""Gallery panel: return distribution of the order book against a normal law."""

import numpy as np
from scipy import stats

from modelly.zoo.order_book.model import OrderBook, OrderBookScenario

BINS = 41


def draw(ax):
    """Histogram of standardised mid-price returns, log scale, with a normal density."""
    model = OrderBook(OrderBookScenario(rng=1))
    model.run()
    returns = model.returns()
    z = (returns - returns.mean()) / returns.std()
    ax.hist(z, bins=BINS, density=True, label="simulated")
    grid = np.linspace(z.min(), z.max(), 200)
    ax.plot(grid, stats.norm.pdf(grid), "k--", label="normal")
    ax.set_yscale("log")
    ax.set_xlabel("standardised return")
    ax.set_ylabel("density")
    ax.set_title(f"excess kurtosis {stats.kurtosis(returns):.1f}")
    ax.legend(frameon=False)
