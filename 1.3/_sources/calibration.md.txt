# Calibration

`modelly.calibrate` fits a model's parameters to observed data and says how sure the fit is. You
give priors over the parameters and targets (an observed series, or summary statistics of one);
a method runs the model many times through the [experiment executors](experiments.md) and
returns a posterior: weighted parameter samples, their summaries, plots and predictions.

| Method | What it returns | Use it when |
|---|---|---|
| `ABCSMC` | a posterior distribution | the default: approximate Bayesian computation by sequential Monte Carlo |
| `ABCRejection` | a posterior distribution | a quick first look, or a cheap model |
| `SimulatedMoments` | the best point | you match moments (means, variances, autocorrelations) of series |
| `BayesOpt` | the best point | each run is expensive and you can afford only tens of them |

Every run is written to a Parquet store like an experiment's, so the store needs the
`experiments` extra:

```bash
pip install "modelly-abm[experiments]"
```

## A worked example: an SIR model and case data

The model lives in its own file, `epidemic.py`, so that worker processes can import it:

```python
import math

from modelly import Model
from modelly.scenarios import Scenario


class EpidemicScenario(Scenario):
    beta: float = 0.4  # infection rate
    gamma: float = 0.1  # recovery rate
    population: int = 1000
    initial: int = 10


class Epidemic(Model):
    """A stochastic SIR model: binomial infections and recoveries each day."""

    def __init__(self, scenario: EpidemicScenario = EpidemicScenario):
        super().__init__(scenario=scenario)
        self.susceptible = scenario.population - scenario.initial
        self.infected = scenario.initial
        self.recovered = 0

    def step(self):
        s = self.scenario
        pressure = 1 - math.exp(-s.beta * self.infected / s.population)
        infections = int(self.rng.binomial(self.susceptible, pressure))
        recoveries = int(self.rng.binomial(self.infected, 1 - math.exp(-s.gamma)))
        self.susceptible -= infections
        self.infected += infections - recoveries
        self.recovered += recoveries
```

The "case data" here are 40 days of one run at `beta = 0.4`, `gamma = 0.1`; in a real study
they come from a file (`pandas.read_csv("cases.csv")["cases"]`).

```python
from epidemic import Epidemic, EpidemicScenario

from modelly.calibrate import ABCSMC, Prior, Target

truth = Epidemic(EpidemicScenario(beta=0.4, gamma=0.1, rng=99))
cases = []
for day in range(40):
    truth.step()
    cases.append(truth.infected)

calibration = ABCSMC(
    model=Epidemic,
    priors={"beta": Prior.uniform(0.05, 1.0), "gamma": Prior.uniform(0.02, 0.5)},
    targets=[Target("infected", observed=cases)],
    steps=40,
    particles=100,
    seed=2027,
)

if __name__ == "__main__":  # process workers re-import this script on Windows and macOS
    posterior = calibration.run(generations=6, executor="processes", max_parallel=4)
    print(posterior.summary().round(3))
    print(calibration.trace().round(3))
```

```text
        mean  median     sd  hdi_low  hdi_high
beta   0.423   0.420  0.063    0.332     0.553
gamma  0.098   0.096  0.020    0.067     0.139

   generation  tolerance  acceptance      ess  runs
0           0        inf       1.000  100.000   100
1           1    234.254       0.333   98.564   300
2           2    194.326       0.250   98.173   400
3           3    157.520       0.250   90.862   400
4           4    114.285       0.167   98.561   600
5           5     83.620       0.250   96.691   400
```

The 95 % highest-density intervals contain the true values. Each generation lowers the
tolerance (the largest accepted distance to the data) and costs more runs to fill; more
generations, or more particles, narrow the posterior further.

```python
posterior.plot().savefig("fit.png")  # marginals, pairs, and the fit against the data
posterior.to_dataframe()  # beta, gamma, weight, distance: one row per particle
posterior.best  # the particle closest to the data
posterior.predict(
    draws=20
)  # 20 new runs at posterior samples: draw, replicate, step, infected
```

`plot()` returns a Matplotlib figure: weighted histograms of each parameter, scatter plots of
each pair, and for each target the observed values against the posterior median and the 95 %
band of the particles' simulations.

## Priors

| Prior | Parameters |
|---|---|
| `Prior.uniform(low, high)` | every value in the interval equally likely |
| `Prior.log_uniform(low, high)` | uniform on a log scale, `low > 0` |
| `Prior.normal(mean, sd)` | |
| `Prior.log_normal(mu, sigma)` | the logarithm is normal |
| `Prior.truncated_normal(mean, sd, low, high)` | a normal cut to an interval |
| `Prior.choice(values, probabilities=None)` | one of a list, for discrete parameters |

`prior.sample(rng, n)` draws from a numpy generator and `prior.logpdf(x)` is the log density
(`-inf` off the support). Parameters the model needs but you do not fit go to `fixed=`:
`ABCSMC(..., fixed={"population": 5000})`. When the model's `scenario` argument defaults to a
`Scenario` class, the names and types are checked against it before anything runs.

## Targets and distances

`Target(name, observed, distance=..., weight=..., summary=..., output=...)`:

- `name` is what the model records every step, read like an [experiment
  output](experiments.md#outputs): an attribute, a property or a method of the model. A model
  reporter of a `DataCollector` that reads an attribute reads the same thing. `output=` names
  something else to record (a dotted path or a module-level function of the model).
- Without `summary`, `observed` is a series matched to the end of the simulated one: its last
  value against the state after the last step. 40 observed values and `steps=40` compare days 1
  to 40.
- With `summary`, a function of one run's series (step 0 first) returns the statistics compared
  with `observed`: `Target("infected", observed=[455], summary=numpy.max)` fits the peak.
- With `replicates=` above 1, the replicates' summaries are averaged before the distance.
- The total distance is the sum of the targets' `weight * distance`, which fits several
  patterns at once (pattern-oriented modelling).

| Distance | |
|---|---|
| `distance.rmse` (default), `"rmse"` | root mean squared error |
| `distance.mae`, `"mae"` | mean absolute error |
| `distance.euclidean`, `"euclidean"` | the norm of the difference, for vectors of statistics |
| `distance.weighted(weights)` | a weighted RMSE, one weight per value |
| `distance.wasserstein`, `"wasserstein"` | Wasserstein-1 between the two sets of values (scipy) |
| any `f(simulated, observed) -> float` | your own |

Counts that span orders of magnitude fit better on a log scale:
`Target("prey", numpy.log1p(counts), summary=log_counts)` with a module-level
`def log_counts(series): return numpy.log1p(series[1:])`.

## ABC-SMC

Generation 0 samples the priors and accepts every particle. Each later generation sets its
tolerance to the `quantile` (default 0.5) of the previous distances, draws ancestors by weight
and moves them with a perturbation kernel, keeps the particles within the tolerance and weights
them by prior density over proposal density. The kernel is a multivariate normal with twice the
weighted covariance of the previous population for continuous parameters; a choice keeps its
value with probability 0.7 and otherwise jumps to another value. The effective sample size of
the weights is in `trace()` and `posterior.effective_sample_size`.

`run()` stops at the first of:

| Rule | Set with |
|---|---|
| a number of generations | `run(generations=5)` |
| a budget of model runs | `run(budget=20_000)`; a generation that would exceed it is not started |
| a tolerance reached | `ABCSMC(..., min_tolerance=10.0)` |
| an acceptance rate too low | `ABCSMC(..., min_acceptance=0.01)` (the default) |

`posterior.info["stopped"]` says which one.

## Seeds, executors and resuming

A calibration's `seed` is the root of every random stream: the priors' draws, the proposals of
each batch and the seeds of every run (`SeedSequence(seed, spawn_key=...)`, as in experiments).
Proposals are made in batches of `particles`, and a generation keeps the first accepted
particles in proposal order, so the posterior is the same on `"serial"`, `"threads"`,
`"processes"`, Dask, Ray or a cluster, with any number of workers, and with the compiled core
or `MODELLY_PURE_PYTHON=1`. With `"processes"`, the workers are started once and reused for
every batch of the run.

A run can stop and resume:

```python
calibration.run(generations=3)
calibration.save("sir.ckpt")

# later, possibly in another process
calibration = ABCSMC.load("sir.ckpt")
posterior = calibration.run(
    generations=6
)  # identical to one uninterrupted 6-generation run
```

`run(..., checkpoint="sir.ckpt")` saves after every generation. A run stopped by its budget
in the middle of a generation resumes from the last whole generation and repeats the same
proposals, so the result is still identical. With `store="runs/sir"` the runs themselves are
kept, and a rerun reads them instead of running them again.

```{warning}
A calibration checkpoint is a pickle, like a [model checkpoint](checkpoints.md): only load
files you wrote or otherwise trust. Distances, summaries and outputs must be module-level
functions (not lambdas) for the calibration to be saved.
```

## ABC rejection

```python
from modelly.calibrate import ABCRejection

rejection = ABCRejection(Epidemic, priors, targets, steps=40, seed=1)
posterior = rejection.run(budget=2000, quantile=0.05)  # keep the closest 5 %
posterior = rejection.run(
    budget=2000, tolerance=150.0
)  # or every run within a distance
```

All `budget` samples run as one batch; the accepted ones have equal weights.

## Simulated method of moments

Each target gives moments (a series, or the statistics of its `summary`); the objective is
`g' W g` with `g` the gap between the replicate mean of the simulated moments and the observed
ones. It is minimised with `scipy.optimize` (`optimizer="Nelder-Mead"` or `"Powell"`) over the
priors' box (their support, or the central 99.8 % of an unbounded prior; log-scaled priors on a
log scale). Every evaluation uses the same replicate seeds (common random numbers), so the
optimiser sees a deterministic function.

```python
from modelly.calibrate import SimulatedMoments

fit = SimulatedMoments(
    Market, priors, targets, steps=200, replicates=8, weighting="diagonal", seed=3
)
estimate = fit.run(evaluations=150)
estimate.best  # the parameters
fit.trace()  # every evaluation and its objective
```

`weighting` is `"identity"`, `"diagonal"` (inverse variances of the moments), `"optimal"`
(inverse covariance), both estimated from the replicates at the start point, or a matrix.

## Bayesian optimisation

`BayesOpt` is a basic optimiser built on numpy and scipy, with no extra library: a Latin
hypercube of `initial` points, then one point at a time, the candidate with the largest
expected improvement under a Gaussian process (squared-exponential kernel with one length scale
per parameter) fitted to the evaluations so far. It minimises the targets' total distance with
common random numbers and returns the best point. It suits a handful of parameters and up to a
few hundred evaluations; for more, use a dedicated optimisation library on the same objective.

```python
from modelly.calibrate import BayesOpt

search = BayesOpt(Epidemic, priors, targets, steps=40, replicates=4, seed=3)
search.run(evaluations=40, initial=10).best
```

## From the command line

A calibration can live in a TOML file that reuses the [experiment format](experiments.md#from-the-command-line):

```toml
[experiment]
model = "epidemic.py:Epidemic"   # relative to this file, or package.module:Class
steps = 40
seed = 2027
store = "runs/calibration"       # optional; a temporary folder otherwise

[space]                          # a range is a uniform prior (log = true: log-uniform),
beta = { min = 0.05, max = 1.0 } # an integer range or a list a choice,
population = 1000                # anything else a fixed parameter

[priors]                         # other priors, by kind and arguments
gamma = { kind = "truncated_normal", mean = 0.15, sd = 0.1, low = 0.01, high = 0.5 }

[[targets]]
name = "infected"
file = "cases.csv"               # or observed = [...]; column defaults to the name
column = "cases"
distance = "rmse"                # or mae, euclidean, wasserstein, module:function

[calibration]
method = "abc_smc"               # abc_rejection, simulated_moments, bayes_opt
particles = 100                  # the method's settings
generations = 6                  # and its run() arguments
budget = 5000

[run]
executor = "processes"
max_parallel = 4
```

```bash
modelly calibrate sir.toml
modelly calibrate sir.toml --output posterior.csv     # every sample with its weight
modelly calibrate sir.toml --checkpoint sir.ckpt      # resumes when the file exists
```

It prints the summary and the run's diagnostics. Exit status: 0 when the calibration finished,
1 when a run failed or no sample was accepted, 2 for a bad command line or spec.
`python -m modelly.calibrate` is the same command; `--help` shows the whole reference.
