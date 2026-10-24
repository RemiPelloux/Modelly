"""Continuous double auction: a zero-intelligence limit order book.

Prices are integer ticks. The book keeps, for every tick, the number of resting buy orders
(bids) and sell orders (asks) of one unit each. Order flow is random, as in the
zero-intelligence model of Farmer, Patelli and Zovko: each event is, with probabilities in
proportion to its rate,

* a market buy or sell (rate ``market_rate / 2`` each): it takes one unit at the best
  opposite price;
* a limit buy or sell (rate ``limit_rate / 2`` each): it rests at a price drawn uniformly
  ``1 .. window`` ticks away from the opposite best quote, on its own side of it (a buy
  below the best ask, a sell above the best bid), so it never crosses;
* a cancellation (rate ``cancel_rate`` per resting order): a uniformly random resting
  order leaves the book.

A side is never emptied: an event that would remove its last order becomes a limit order
on that side. A step is ``events`` events; the mid price is recorded after each step.

Validation: the stylised fact of fat tails (Cont, 2001). The excess kurtosis of mid-price
returns is positive, far above the ``sqrt(24 / n)`` standard error it would have if
returns were normal. The spread is at least one tick at all times.

References:
    Farmer, J. D., Patelli, P. and Zovko, I. I. (2005). The predictive power of zero
    intelligence in financial markets. PNAS, 102(6), 2254-2259.

    Cont, R. (2001). Empirical properties of asset returns: stylized facts and
    statistical issues. Quantitative Finance, 1, 223-236.
"""

from __future__ import annotations

import numpy as np

from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario

HALF = 0.5
# Event kinds, in the order of their rates in ``OrderBook.rates``.
MARKET_BUY, MARKET_SELL, LIMIT_BUY, LIMIT_SELL, CANCEL_BID, CANCEL_ASK = range(6)


class OrderBookScenario(Scenario):
    """Parameters of the zero-intelligence order book.

    Attributes:
        ticks: number of price levels.
        window: limit orders rest 1 .. window ticks from the opposite best quote.
        market_rate: rate of market orders (both sides together).
        limit_rate: rate of limit orders (both sides together).
        cancel_rate: rate of cancellation per resting order.
        initial_depth: orders per level in the ``window`` levels of each side at start.
        events: order events per step.
        steps: default run length used by ``run``.
    """

    ticks: int = 1000
    window: int = 20
    market_rate: float = 0.3
    limit_rate: float = 1.0
    cancel_rate: float = 0.005
    initial_depth: int = 2
    events: int = 10
    steps: int = 2000


class OrderBook(Model):
    """A limit order book fed by random order flow.

    Example:
        >>> model = OrderBook(OrderBookScenario(rng=1, steps=50))
        >>> model.run()
        >>> bool(model.best_ask() > model.best_bid())
        True
    """

    def __init__(self, scenario: OrderBookScenario = OrderBookScenario) -> None:
        """Fill ``window`` levels on each side of the middle of the price grid."""
        super().__init__(scenario=scenario)
        s = self.scenario
        self.bids = np.zeros(s.ticks, dtype=np.int64)
        self.asks = np.zeros(s.ticks, dtype=np.int64)
        middle = s.ticks // 2
        self.bids[middle - s.window : middle] = s.initial_depth
        self.asks[middle + 1 : middle + 1 + s.window] = s.initial_depth
        self.datacollector = DataCollector(
            model_reporters={"mid": mid_price, "spread": spread}
        )
        self.datacollector.collect(self)

    def best_bid(self) -> int:
        """Highest price with a resting buy order."""
        return int(np.flatnonzero(self.bids)[-1])

    def best_ask(self) -> int:
        """Lowest price with a resting sell order."""
        return int(np.flatnonzero(self.asks)[0])

    def mid(self) -> float:
        """Mid price, halfway between the best quotes."""
        return HALF * (self.best_bid() + self.best_ask())

    def rates(self) -> np.ndarray:
        """Rates of the six event kinds in the current book."""
        s = self.scenario
        market, limit = HALF * s.market_rate, HALF * s.limit_rate
        bids, asks = self.bids.sum(), self.asks.sum()
        cancels = (s.cancel_rate * bids, s.cancel_rate * asks)
        return np.array([market, market, limit, limit, *cancels])

    def step(self) -> None:
        """``events`` order events, then record the mid price."""
        for _ in range(self.scenario.events):
            self.event()
        self.datacollector.collect(self)

    def event(self) -> None:
        """Draw one event kind in proportion to its rate and apply it."""
        rates = self.rates()
        kind = int(np.searchsorted(np.cumsum(rates), self.rng.random() * rates.sum()))
        if kind in (MARKET_BUY, CANCEL_ASK) and self.asks.sum() == 1:
            kind = LIMIT_SELL
        elif kind in (MARKET_SELL, CANCEL_BID) and self.bids.sum() == 1:
            kind = LIMIT_BUY
        if kind == MARKET_BUY:
            self.asks[self.best_ask()] -= 1
        elif kind == MARKET_SELL:
            self.bids[self.best_bid()] -= 1
        elif kind in (LIMIT_BUY, LIMIT_SELL):
            self.limit(buy=kind == LIMIT_BUY)
        else:
            self.cancel(self.bids if kind == CANCEL_BID else self.asks)

    def limit(self, buy: bool) -> None:
        """Rest one order ``1 .. window`` ticks inside the opposite best quote."""
        s = self.scenario
        offset = int(self.rng.integers(1, s.window + 1))
        if buy:
            self.bids[max(self.best_ask() - offset, 0)] += 1
        else:
            self.asks[min(self.best_bid() + offset, s.ticks - 1)] += 1

    def cancel(self, side: np.ndarray) -> None:
        """Remove one uniformly random resting order of ``side``."""
        cumulative = np.cumsum(side)
        pick = int(self.rng.integers(cumulative[-1]))
        side[int(np.searchsorted(cumulative, pick, side="right"))] -= 1

    def returns(self) -> np.ndarray:
        """Log returns of the mid price from one step to the next."""
        mids = self.datacollector.get_model_vars_dataframe()["mid"].to_numpy()
        return np.diff(np.log(mids))

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` steps (the scenario's ``steps`` by default)."""
        self.run_for(self.scenario.steps if steps is None else steps)


def mid_price(model: OrderBook) -> float:
    """The mid price (a model reporter)."""
    return model.mid()


def spread(model: OrderBook) -> int:
    """The bid-ask spread in ticks (a model reporter)."""
    return model.best_ask() - model.best_bid()
