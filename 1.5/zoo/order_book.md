# Continuous double auction (zero-intelligence order book)

**Field:** economics · **Zoo name:** `order_book` · **Module:** `modelly.zoo.order_book.model`

![Mid price and the distribution of its returns](https://remipelloux.github.io/Modelly/_images/order_book.png)

A limit order book on an integer price grid, fed by random order flow, as in the zero-intelligence model of Farmer, Patelli and Zovko. With probabilities in proportion to their rates, an event is a market buy or sell, which takes one unit at the best opposite price; a limit buy or sell, which rests at a price drawn uniformly `1 .. window` ticks inside the opposite best quote, so it never crosses; or the cancellation of a uniformly random resting order. No trader has a strategy, yet the prices show some of the stylised facts of real markets.

## How it is written

The book is two numpy arrays of depth per tick, `bids` and `asks`; the best quotes are the last and first non-empty levels. Each event draws its kind from the six rates (`model.rates()`), and a cancellation picks its order in proportion to depth with one `cumsum` and `searchsorted`. An event that would empty a side becomes a limit order on that side. A step is `events` events; the mid price and the spread are collected after each step.

```python
from modelly.zoo.order_book.model import OrderBook, OrderBookScenario

model = OrderBook(OrderBookScenario(rng=42))
model.run()
model.best_bid(), model.best_ask()
model.returns()  # log returns of the mid price, step to step
model.datacollector.get_model_vars_dataframe()  # mid price and spread per step
```

Parameter

Default

Meaning

ticks

1000

number of price levels

window

20

limit orders rest 1 .. window ticks from the opposite best quote

market_rate

0.3

rate of market orders, both sides together

limit_rate

1.0

rate of limit orders, both sides together

cancel_rate

0.005

rate of cancellation per resting order

initial_depth

2

orders per level in the window levels of each side at start

events

10

order events per step

steps

2000

run length of run()

## Validation

Real returns have fat tails: their excess kurtosis is positive (Cont, 2001). `tests/zoo/test_order_book.py` runs 2,000 steps with three seeds and checks the excess kurtosis of the mid-price returns is above five times `sqrt(24 / n)`, its standard error if the returns were normal; it is about thirty standard errors in practice. It also checks the spread is always at least one tick, that aggressive market orders never empty a side of a one-order book, and that the same seed gives the same price path.

## Model card: Continuous double auction (zero-intelligence order book)

A limit order book on an integer price grid fed by random market, limit and cancel orders, in the zero-intelligence style of Farmer, Patelli and Zovko: no trader has a strategy, yet returns have fat tails.

**Model:** `modelly.zoo.order_book.model:OrderBook` · **Validated:** 2026-11-03 with Modelly 1.4.3, on source `23303fbeaf51`

### Intended use

- Teaching how a limit order book works: best quotes, the spread, market orders that take liquidity and limit orders that provide it.
- Showing that a stylised fact (fat-tailed returns) can come from the mechanics of the book alone, with no strategic traders.
- A starting point for order-book models, with a validated core to extend (order sizes, informed traders, other placement rules).

### Out-of-scope use

- Forecasting prices or returns of a real asset: the order flow is random and nothing is calibrated to market data.
- Designing or testing trading strategies: there are no strategic traders, and the book does not respond to them as a real market would.
- Claims about stylised facts beyond fat tails (volatility clustering, the shape of the spread distribution): the tests check only kurtosis and a valid book.

### Data

- None by default: the price grid, the order rates and the initial depth are illustrative values in `OrderBookScenario`.

### Validation

Check

Test

excess kurtosis of mid-price returns above five times its sqrt(24 / n) standard error under normal returns (three seeds)

tests/zoo/test_order_book.py::test_returns_have_fat_tails

the spread is at least one tick at every step and no level holds a negative number of orders

tests/zoo/test_order_book.py::test_spread_is_at_least_one_tick

aggressive market orders never empty a side of a one-order book; same seed, same price path

tests/zoo/test_order_book.py

### Known limits

- Every order is one unit and limit prices are uniform within `window` ticks of the opposite best quote; real order sizes and placements are far from uniform.
- Order flow is zero-intelligence: rates do not depend on prices, the spread or past returns.
- A side is never emptied: an event that would remove its last order becomes a limit order on that side, which a real book does not guarantee.
- Prices live on a fixed grid of `ticks` levels; limit orders that would fall outside it are clipped to its edges.

### Ethical considerations

- This is a toy market; results presented as evidence about a real market or a regulation (tick sizes, cancellation rules) would overstate what it shows.

## References

- Farmer, J. D., Patelli, P. and Zovko, I. I. (2005). The predictive power of zero intelligence in financial markets. *PNAS*, 102(6), 2254-2259.
- Cont, R. (2001). Empirical properties of asset returns: stylized facts and statistical issues. *Quantitative Finance*, 1, 223-236.

Start a project from it with `modelly zoo copy order_book my_market`.
