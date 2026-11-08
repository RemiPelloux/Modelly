# Bouchaud-Mezard wealth condensation

**Field:** economics · **Zoo name:** `bouchaud_mezard` · **Module:** `modelly.zoo.bouchaud_mezard.model`

![Gini against the inverse-gamma prediction](https://remipelloux.github.io/Modelly/dev/_images/bouchaud_mezard.png)

Each agent earns a random return on its wealth and exchanges with everybody else. In the mean-field version, `dW_i = J (mean(W) - W_i) dt + sigma W_i dB_i` (Ito): returns of variance `sigma^2` per unit time, and an exchange that pulls each wealth toward the mean at rate `J`. The more noise relative to exchange, the more the wealth condenses into a few hands.

## How it is written

Wealth is a `Column` on the `Saver` agent class. A step of length `dt` applies the multiplicative part exactly, `W <- W exp(sigma sqrt(dt) xi - sigma^2 dt / 2)` (mean preserving, never negative), then the exchange `W <- W + J dt (mean(W) - W)`, then divides by the mean, so `model.wealth` is wealth relative to the mean. Each part is one numpy expression over the column.

```python
from modelly.zoo.bouchaud_mezard.model import BouchaudMezard, BouchaudMezardScenario

model = BouchaudMezard(BouchaudMezardScenario(rng=42, volatility=1.0))
model.run()
model.stationary_shape()  # alpha = 1 + 2 J / sigma^2
model.datacollector.get_model_vars_dataframe()  # Gini per step
```

Parameter

Default

Meaning

n

2000

number of agents

exchange

1.0

exchange rate J per unit time

volatility

1.0

sigma, standard deviation of returns per unit time

dt

0.01

step length; exchange * dt must be below one

steps

2000

run length of run()

## Validation

The Fokker-Planck equation of the relative wealth `w` has the stationary density `P(w) ~ exp(-(alpha - 1) / w) / w^(1 + alpha)`: an inverse-gamma law with shape `alpha = 1 + 2 J / sigma^2` and mean one, whose tail is a Pareto law of exponent `alpha`. Bouchaud and Mezard write the noise variance as `2 sigma^2`, hence their `mu = 1 + J / sigma^2`.

`tests/zoo/test_bouchaud_mezard.py` runs 2,000 agents for ten relaxation times, then takes twenty spaced snapshots, for `sigma^2 / J` = 0.5, 1 and 1.5 (shapes 5, 3 and 7/3, all of finite variance) and two seeds. The mean Gini must be within three single-snapshot standard deviations of the Gini of the inverse-gamma law, computed by quadrature of its Lorenz identity `G = 1 - int (1 - F)^2`. Both the analytic and the simulated Gini must rise with `sigma^2 / J`. It also checks that an unstable step length is rejected and that the same seed gives the same run.

## Model card: Bouchaud-Mezard wealth condensation

Each agent earns a random multiplicative return and exchanges with everybody at a mean-field rate; relative wealth settles to an inverse-gamma law with a Pareto tail that fattens as noise grows against exchange.

**Model:** `modelly.zoo.bouchaud_mezard.model:BouchaudMezard` · **Validated:** 2026-11-03 with Modelly 1.4.3, on source `94dd3213e573`

### Intended use

- Teaching how multiplicative returns concentrate wealth and how exchange between agents holds that concentration back.
- Comparing inequality (the Gini coefficient) across noise-to-exchange ratios against an analytic stationary law.
- A starting point for wealth models with multiplicative noise, with a validated core to extend (networks of exchange, taxes, heterogeneous returns).

### Out-of-scope use

- Describing or forecasting a real economy’s wealth distribution: the rates are illustrative and nothing is calibrated.
- Recommending tax or redistribution levels: the exchange term is a stylised mean-field pull, not a policy instrument.
- Regimes with sigma^2 / J of 2 or more (shape alpha of 2 or less): the stationary law then has infinite variance and the tests do not cover it.

### Data

- None by default: the number of agents, the exchange rate, the volatility and the step length are illustrative values in `BouchaudMezardScenario`.

### Validation

Check

Test

time-averaged Gini within three single-snapshot standard deviations of the inverse-gamma law’s Gini, for sigma^2 / J = 0.5, 1 and 1.5 (two seeds)

tests/zoo/test_bouchaud_mezard.py::test_gini_matches_inverse_gamma

both the analytic and the simulated Gini rise with sigma^2 / J

tests/zoo/test_bouchaud_mezard.py::test_gini_rises_with_inequality

shape alpha = 1 + 2 J / sigma^2; an unstable step is rejected; wealth stays positive with mean one; same seed, same run

tests/zoo/test_bouchaud_mezard.py

### Known limits

- Mean-field exchange: every agent exchanges with the average of everybody, with no network or local structure.
- Returns are independent across agents and in time, with the same volatility for everyone.
- Wealth is reported relative to the mean, so growth of total wealth is not modelled; the step `dt` adds a small discretisation bias.
- The validation is of the stationary Gini only, for sigma^2 / J = 0.5, 1 and 1.5, not of the time course.

### Ethical considerations

- Results can be read as saying wealth concentration is inevitable or that more exchange is the remedy; present them as properties of this stylised model, not of a real economy.

## References

- Bouchaud, J.-P. and Mezard, M. (2000). Wealth condensation in a simple model of economy. *Physica A*, 282, 536-545.

Start a project from it with `modelly zoo copy bouchaud_mezard my_economy`.
