# Live data and data assimilation

A digital twin is a model that keeps up with the system it stands for: every time new data
arrives, the model's picture of the present is corrected, and its forecast starts again from
there. `modelly.stream` (provisional, new in 1.4) does this for agent-based models in three
parts:

- **sources** hand out observations as they arrive: a table in memory, a growing CSV file, an
  HTTP endpoint, an MQTT or a Kafka topic;
- an **observation operator** reads the same quantities from a model;
- an **ensemble** of replicates runs in lock step, and a **filter** keeps it close to the
  observations: a particle filter weights and resamples whole runs, an ensemble Kalman filter
  adjusts continuous parameters.

This page is a nowcasting tutorial. A synthetic "truth" run plays the world; we observe its
daily case counts with noise and ask the filters what is happening now (the number currently
infected, which nobody observes), what will happen next, and what the contact rate is. The code
runs as is, top to bottom; the test suite runs it too (`tests/stream/test_assimilation_tutorial.py`).

## A small epidemic

```python
import math

import numpy as np

from modelly import Agent, Model
from modelly.scenarios import Scenario


class TownScenario(Scenario):
    people: int = 1000
    seeded: int = 10  # infected on day 0
    beta: float = 0.3  # infections per infected person and day, in a susceptible town
    recovery: float = 0.15  # chance of recovering each day


class Person(Agent):
    def __init__(self, model, infected):
        super().__init__(model)
        self.infected = infected
        self.recovered = False


class Town(Model):
    def __init__(self, scenario):
        super().__init__(scenario=scenario)
        self.beta = scenario.beta  # an attribute, so a filter can adjust it
        self.new_cases = 0
        for i in range(scenario.people):
            Person(self, infected=i < scenario.seeded)

    def step(self):
        people = list(self.agents)
        chance = 1 - math.exp(-self.beta * self.prevalence / len(people))
        draw = self.random.random
        self.new_cases = 0
        for person in people:
            if person.infected:
                if draw() < self.scenario.recovery:
                    person.infected, person.recovered = False, True
            elif not person.recovered and draw() < chance:
                person.infected = True
                self.new_cases += 1

    @property
    def prevalence(self):
        return sum(person.infected for person in self.agents)
```

The contact rate lives on the model as `self.beta`, read at every step: that is what lets a
filter set it on a running replicate.

## The truth and its observations

The truth is one run with `beta = 0.45`. Each day we record the new cases plus Gaussian noise of
standard deviation 3, and keep the true prevalence aside to score the filters later.

```python
DAYS = 50
NOISE = 3.0

truth = Town(TownScenario(rng=1, beta=0.45))
noise = np.random.default_rng(99)
records, true_prevalence = [], []
for day in range(1, DAYS + 1):
    truth.step()
    records.append({"time": day, "cases": truth.new_cases + noise.normal(0, NOISE)})
    true_prevalence.append(truth.prevalence)
```

```python
from modelly.stream import ObservationOperator, ReplaySource

observe = ObservationOperator(cases=lambda model: model.new_cases)
infected = ObservationOperator(infected=lambda model: model.prevalence)
```

`ReplaySource(records)` replays the table; in a live twin the same loop polls a `CSVSource`
that a data pipeline appends to, an `HTTPSource`, or a broker (see [Live sources](#live-sources)).
`observe` maps a model to what the world reports; `infected` reads what we want to know but
never see.

## An ensemble

An `Ensemble` builds `n` replicates of one scenario, each with a seed spawned from the
scenario's (replicate `i` has the seed `Scenario.spawn_replications(n)[i]` would give it).
We do not know the contact rate, so each replicate draws its own from a prior: anything
between 0.2 and 0.8.

```python
from modelly.stream import Ensemble

REPLICATES = 40
prior = {"beta": lambda rng: rng.uniform(0.2, 0.8)}

filtered = Ensemble(Town, TownScenario(rng=2), REPLICATES, prior=prior)
free = Ensemble(Town, TownScenario(rng=2), REPLICATES, prior=prior)
```

`free` is the same ensemble left alone: it shows what the model knows without the data.

## Particle filter

The particle filter (Gordon, Salmond & Smith 1993) treats each replicate as a particle. At each
observation it runs the replicates to the observation's time, weights each by the likelihood
of the observation (`ObservationOperator.log_likelihood`, Gaussian errors of standard deviation
`sd`), and when the weights become too uneven it resamples: replicates with little weight are
dropped and the likely ones duplicated. The test of unevenness is the effective sample size
(ESS) `1 / sum(w**2)`; the filter resamples when it falls below `threshold * n` (half the
ensemble by default), with systematic resampling (Douc & Cappé 2005). A duplicate is a
checkpoint copy of the whole model, agents and events included, reseeded so that it goes its
own way from the next draw on.

```python
from modelly.stream import ParticleFilter

pf = ParticleFilter(filtered, observe, sd=NOISE)

errors_filtered, errors_free = [], []
for observation in ReplaySource(records).poll():
    pf.assimilate(observation)
    free.advance(observation.time)
    now = true_prevalence[int(observation.time) - 1]
    errors_filtered.append(pf.estimate(infected)["infected"] - now)
    errors_free.append(free.values(infected).mean() - now)


def rmse(errors):
    return float(np.sqrt(np.mean(np.square(errors))))


rmse_filtered, rmse_free = rmse(errors_filtered), rmse(errors_free)
```

`pf.estimate(infected)` is the weighted mean of the hidden prevalence across replicates: the
nowcast. Over the 50 days its root mean square error is about 5 people for the filtered ensemble
(`rmse_filtered`) against about 69 for the free one (`rmse_free`): the free replicates, with contact rates spread
over the prior, peak at different times and heights, while the filter keeps the runs whose
case counts agree with the data. `pf.history` has one row per observation (time, ESS, whether
it resampled, and the log evidence `log p(y_t | y_<t)`, whose sum estimates the log marginal
likelihood of the data); `pf.resamplings` counts the resamplings.

The replicates that survive also carry a contact rate (0.47 here):

```python
pf_beta = float(np.average([model.beta for model in filtered], weights=pf.weights))
```

A particle filter learns a fixed parameter only by keeping the replicates that drew a good one:
after many resamplings few distinct values remain. The ensemble Kalman filter below is the
tool for parameters.

## Bands now and ahead

`band` and `forecast` give the spread of any operator across the (weighted) replicates as a
plain DataFrame, one row per time and quantity, with the mean and the quantiles you ask for
(5%, 50% and 95% by default). This is what a plot, a report or Studio's live view reads.

```python
now = pf.band(infected)
ahead = pf.forecast(DAYS + 14, infected, quantiles=(0.05, 0.25, 0.5, 0.75, 0.95))
```

```text
    time  quantity       mean  q0.05  q0.25  q0.5  q0.75  q0.95
0   50.0  infected  14.6    9.0   12.0  14.0   16.3   20.9
1   51.0  infected  12.6    8.0   10.0  13.0   14.0   19.0
...
14  64.0  infected   2.0    0.0    1.0   2.0    3.0    4.9
```

The forecast runs checkpoint copies of the replicates; the ensemble itself stays at day 50,
ready for tomorrow's observation. Weighted quantiles place each replicate's weight at the
midpoint of its step in the cumulative weights and interpolate (the Hazen definition when the
weights are equal).

## Ensemble Kalman filter for the contact rate

The ensemble Kalman filter (Evensen 1994, 2003) treats the parameters as part of the state
(state/parameter augmentation). At each observation it runs the replicates on, then shifts each
replicate's parameters by the Kalman gain estimated from the ensemble, `cov(beta, cases)`
over `var(cases) + sd**2`, times the gap between a perturbed observation and what that replicate
predicted. The perturbations (Burgers, van Leeuwen & Evensen 1998) keep the ensemble's spread
right; they come from a generator derived from the scenario's seed, so the filter is
deterministic.

```python
from modelly.stream import EnsembleKalmanFilter

ensemble = Ensemble(Town, TownScenario(rng=3), REPLICATES, prior=prior)
enkf = EnsembleKalmanFilter(
    ensemble,
    observe,
    sd=2 * NOISE,
    parameters=["beta"],
    bounds={"beta": (0.0, 2.0)},
)
enkf.run(ReplaySource(records))
beta_estimate = enkf.estimate()["beta"]
```

The estimate ends at 0.451 against the true 0.45, with a spread of 0.03 across replicates;
`enkf.history` shows the mean and spread of `beta` after each observation. Two things are worth
knowing:

- The filter adjusts attributes, not agents: an agent-based state (who is infected) is not a
  vector it can shift, so replicates whose epidemic is ahead or behind the truth push the
  parameter the wrong way for a while. A larger `sd` than the measurement noise, here twice
  it, makes the filter trust each observation less and absorbs that.
- `bounds` clips each parameter after every update, so a contact rate never goes negative.

## Reproducibility

For a seed, every result above is bit-identical from run to run, with the compiled core or the
pure-Python one (`MODELLY_PURE_PYTHON=1`). The ensemble's seeds are spawned from the scenario's
without changing it, the prior draws, resampling uniforms and Kalman perturbations come from
seed sequences derived from it in domains of their own, and duplicate `slot` of the `g`-th
resampling is reseeded from the key `(g, slot)`. The test suite checks this
(`tests/stream/test_particle.py`). Replicates run one after the other in this process, in
index order; parallel stepping would move models between processes at every observation and is
not done.

Models with per-agent random streams (`agent_streams = True`) resample correctly, but a
duplicate's agents keep the streams of the agents they were copied from: only `model.random`
and `model.rng` are reseeded.

## Live sources

Every source has `poll(until=None)`, which hands out the observations not seen yet, in time
order, each once; a filter's `run(source)` assimilates them. For a broker, install the extra and
point the source at a topic whose messages are JSON records with a `time` field:

```python
# Not run here: it needs a broker.
from modelly.stream import KafkaSource, MQTTSource

# pip install "modelly-abm[mqtt]"
cases = MQTTSource("town/cases", host="broker.example.org")

# or: pip install "modelly-abm[kafka]"
cases = KafkaSource(
    "town-cases",
    config={"bootstrap.servers": "broker.example.org:9092", "group.id": "twin"},
)


def every_morning():
    pf.run(cases)  # yesterday's messages
    return pf.forecast(pf.ensemble.time + 14, infected)  # the next two weeks
```

Call `every_morning` from whatever schedules your jobs and publish the frame it returns;
`close()` on a source releases its connection. `client=` and `consumer=` take a client you
configured yourself (authentication, TLS), or a stand-in in tests. The code of this section
needs a broker, so the test suite does not run it.

## References

- Gordon, N. J., Salmond, D. J. & Smith, A. F. M. (1993). Novel approach to nonlinear/non-Gaussian
  Bayesian state estimation. *IEE Proceedings F*, 140(2), 107-113.
- Douc, R. & Cappé, O. (2005). Comparison of resampling schemes for particle filtering.
  *Proceedings of the 4th International Symposium on Image and Signal Processing and Analysis*,
  64-69.
- Evensen, G. (1994). Sequential data assimilation with a nonlinear quasi-geostrophic model using
  Monte Carlo methods to forecast error statistics. *Journal of Geophysical Research*, 99(C5),
  10143-10162.
- Burgers, G., van Leeuwen, P. J. & Evensen, G. (1998). Analysis scheme in the ensemble Kalman
  filter. *Monthly Weather Review*, 126(6), 1719-1724.
- Evensen, G. (2003). The Ensemble Kalman Filter: theoretical formulation and practical
  implementation. *Ocean Dynamics*, 53(4), 343-367.
