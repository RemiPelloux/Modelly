# Continuous double auction (zero-intelligence order book)

**Field:** economics · **Zoo name:** `order_book` · **Module:** `modelly.zoo.order_book.model`

![Mid price and the distribution of its returns](../images/gallery/order_book.png)

A limit order book on an integer price grid, fed by random order flow, as in the
zero-intelligence model of Farmer, Patelli and Zovko. With probabilities in proportion to
their rates, an event is a market buy or sell, which takes one unit at the best opposite
price; a limit buy or sell, which rests at a price drawn uniformly `1 .. window` ticks
inside the opposite best quote, so it never crosses; or the cancellation of a uniformly
random resting order. No trader has a strategy, yet the prices show some of the stylised
facts of real markets.

## How it is written

The book is two numpy arrays of depth per tick, `bids` and `asks`; the best quotes are the
last and first non-empty levels. Each event draws its kind from the six rates
(`model.rates()`), and a cancellation picks its order in proportion to depth with one
`cumsum` and `searchsorted`. An event that would empty a side becomes a limit order on that
side. A step is `events` events; the mid price and the spread are collected after each step.

```python
from modelly.zoo.order_book.model import OrderBook, OrderBookScenario

model = OrderBook(OrderBookScenario(rng=42))
model.run()
model.best_bid(), model.best_ask()
model.returns()  # log returns of the mid price, step to step
model.datacollector.get_model_vars_dataframe()  # mid price and spread per step
```

| Parameter | Default | Meaning |
|---|---|---|
| `ticks` | `1000` | number of price levels |
| `window` | `20` | limit orders rest `1 .. window` ticks from the opposite best quote |
| `market_rate` | `0.3` | rate of market orders, both sides together |
| `limit_rate` | `1.0` | rate of limit orders, both sides together |
| `cancel_rate` | `0.005` | rate of cancellation per resting order |
| `initial_depth` | `2` | orders per level in the `window` levels of each side at start |
| `events` | `10` | order events per step |
| `steps` | `2000` | run length of `run()` |

## Validation

Real returns have fat tails: their excess kurtosis is positive (Cont, 2001).
`tests/zoo/test_order_book.py` runs 2,000 steps with three seeds and checks the excess
kurtosis of the mid-price returns is above five times `sqrt(24 / n)`, its standard error if
the returns were normal; it is about thirty standard errors in practice. It also checks the
spread is always at least one tick, that aggressive market orders never empty a side of a
one-order book, and that the same seed gives the same price path.

## References

- Farmer, J. D., Patelli, P. and Zovko, I. I. (2005). The predictive power of zero
  intelligence in financial markets. *PNAS*, 102(6), 2254-2259.
- Cont, R. (2001). Empirical properties of asset returns: stylized facts and statistical
  issues. *Quantitative Finance*, 1, 223-236.

Start a project from it with `modelly zoo copy order_book my_market`.
