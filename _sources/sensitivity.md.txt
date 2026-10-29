# Sensitivity analysis

`modelly.sensitivity` says which parameters drive which outputs: screen many parameters cheaply,
then split an output's variance between the few that matter. Every method takes a model (run
through the [experiment executors](experiments.md)), a plain function of the parameters, or an
emulator, and a `ScenarioSpace` whose ranges and choices are the inputs.

| Function | Measures | Runs |
|---|---|---|
| `oat` | the output's range as each parameter moves alone | `levels` per parameter |
| `morris` | elementary effects: `mu`, `mu_star`, `sigma` | `trajectories * (parameters + 1)` |
| `sobol` | first-order `S1` and total `ST` indices, bootstrap intervals | `samples * (parameters + 2)` |
| `pawn` | how much each parameter changes the output's distribution | `samples` |
| `emulate` | a Gaussian-process stand-in for an expensive model | `samples` |

Runs of a model go to a Parquet store, so models need the `experiments` extra
(`pip install "modelly-abm[experiments]"`); functions and emulators do not.

## A worked example: which epidemic parameters matter

The SIR model of the [calibration guide](calibration.md#a-worked-example-an-sir-model-and-case-data)
(`epidemic.py`) has four parameters. Which ones decide how high the epidemic peaks?

```python
from epidemic import Epidemic

from modelly.experiments import Range, ScenarioSpace
from modelly.sensitivity import morris, sobol

space = ScenarioSpace(
    beta=(0.1, 0.8),
    gamma=(0.05, 0.3),
    initial=(1, 30),
    population=Range(500, 2000, integer=True),
)
common = {
    "output": "infected",
    "statistic": "max",
    "steps": 60,
    "replicates": 2,
    "seed": 1,
}

screen = morris(Epidemic, space, trajectories=20, **common)
print(screen.ranking().round(3))
```

```text
                 mu  mu_star    sigma
gamma      -464.850  465.075  408.749
beta        433.800  462.000  370.234
population  408.075  408.975  400.663
initial      85.575   94.575  203.890
```

`output="infected"` records the number infected every step and `statistic="max"` keeps each
run's peak; the two replicates are averaged. `mu_star`, the mean absolute effect of moving a
parameter across a step of its grid, ranks the parameters; a large `sigma` next to it means
the effect depends on where the other parameters are (interactions, non-linearity). The peak
is a head count, so it scales with the population; the size of the first outbreak matters much
less. Recovery and infection rates matter most, in opposite directions (`mu` is negative for
`gamma`).

With the population and the first cases fixed, Sobol indices split the peak's variance between
the two rates:

```python
narrowed = ScenarioSpace(
    beta=(0.1, 0.8), gamma=(0.05, 0.3), initial=10, population=1000
)
indices = sobol(Epidemic, narrowed, samples=256, **common)
print(indices.ranking().round(3))
indices.plot().savefig("sobol.png")
```

```text
          S1     ST  S1_low  S1_high  ST_low  ST_high
beta   0.544  0.576   0.469    0.612   0.495    0.687
gamma  0.423  0.458   0.325    0.514   0.387    0.540
```

`beta` alone explains about half the variance, `gamma` alone about 40 %; `ST - S1`, the share
that comes through interactions, is small for both. The intervals come from 200 bootstrap
resamples; more `samples` narrow them.

## One at a time

```python
from modelly.sensitivity import oat

result = oat(Epidemic, space, levels=5, **common)
result.table  # low, high, effect per parameter
result.sweeps  # every evaluated point: parameter, position, value, output
```

Each parameter takes `levels` evenly spaced values (every value of a choice) while the others
stay at the middle of their ranges. It is the cheapest look and blind to interactions.

## Morris elementary effects

`morris(model, space, output, trajectories=10, levels=4, ...)` draws `trajectories` random
paths on a grid of `levels` values per parameter, each moving one parameter at a time by
`levels / (2 * (levels - 1))` of its range. The elementary effect of a move is the change in the
output divided by the step; `mu` is their mean, `mu_star` the mean of their absolute values and
`sigma` their standard deviation. `plot()` draws `sigma` against `mu_star`.

A ranking is only as stable as the gaps between the effects. On the zoo's Bass diffusion
(innovation, imitation and the number of households) the whole ranking is the same on every seed
with 12 trajectories, and on the age-structured SEIR model the transmission probability comes
first on every seed, three times ahead of the others, while recovery and incubation, whose effects
are of the same size, swap places from seed to seed (`tests/sensitivity/test_morris_stability.py`).
Rerun a screen with two or three seeds before dropping a parameter: one whose rank changes with
the seed is not clearly less important than its neighbour.

## Sobol indices

`sobol(model, space, output, samples=1024, bootstrap=200, confidence=0.95, estimator="jansen")`
uses Saltelli sampling: two matrices `A` and `B` from one scrambled Sobol sequence
(`scipy.stats.qmc`, power-of-two `samples`), and for every parameter the matrix `A` with that
column from `B`.

| `estimator` | `S1` | `ST` |
|---|---|---|
| `"jansen"` (default) | `(V - mean((f(B) - f(AB_i))**2) / 2) / V` | `mean((f(A) - f(AB_i))**2) / 2 / V` |
| `"saltelli"` | `mean(f(B) * (f(AB_i) - f(A))) / V` | `mean(f(A) * (f(A) - f(AB_i))) / V` |

The test suite checks both on the Ishigami function and the Sobol G function, whose indices
are known exactly: every analytical value lies inside its bootstrap interval.

## PAWN

`pawn(model, space, output, samples=500, slices=10, summary="median")` evaluates one Latin
hypercube, cuts each parameter's range into `slices` equal-count slices and compares the
output's distribution in each slice with the unconditional one by the Kolmogorov-Smirnov
statistic. The table gives the `median`, `mean` and `max` over the slices; 0 means the
parameter does not change the output's distribution. Unlike variance-based indices, PAWN does
not assume the variance describes the output well, which matters for skewed or multi-modal
outputs (extinction or outbreak, boom or bust).

## Emulators for expensive models

```python
from modelly.sensitivity import emulate

surrogate = emulate(Epidemic, narrowed, samples=80, **common)
surrogate.r2  # share of variance explained on held-out runs: 0.993 here
sobol(surrogate, narrowed, samples=4096)  # no further model runs
```

`emulate` runs the model at a Latin hypercube of `samples` points and fits a Gaussian process
(the basic numpy and scipy one of `modelly.calibrate.gp`) to the output. The emulator then
stands in for the model in every method. Check `r2` before trusting it: a low value means the
process does not capture the output, and more samples or a narrower space are needed.

## Results

Every function returns a result with:

- `table`: one row per parameter;
- `ranking()`: the table sorted by the main measure (`effect`, `mu_star`, `ST` or the PAWN
  summary), most influential first;
- `to_dataframe()`: the table with the parameter as a column, ready for CSV or Parquet;
- `plot()`: a Matplotlib figure;
- `info`: the number of evaluations and the settings.

## Settings, seeds and executors

`seed`, `steps`, `replicates`, `statistic` (`"last"`, `"max"`, `"min"`, `"mean"`, `"sum"` or a
function of the series), `store`, `executor`, `max_parallel` and `options` (the executor's) are
accepted by every function. The designs and the bootstrap are drawn from the seed, and every
run's seed comes from it as in an experiment, so the indices are the same on every executor and
with any number of workers.

## From the command line

```toml
[experiment]
model = "epidemic.py:Epidemic"   # a Model class, or module:function of the parameters
steps = 60
replicates = 2
seed = 1
outputs = ["infected"]           # the first output is analysed

[space]
beta = { min = 0.1, max = 0.8 }
gamma = { min = 0.05, max = 0.3 }
initial = { min = 1, max = 30 }
population = 1000

[sensitivity]
method = "morris"                # oat, morris, sobol, pawn
statistic = "max"
trajectories = 20                # the method's settings

[run]
executor = "processes"
```

```bash
modelly sensitivity study.toml
modelly sensitivity study.toml --method pawn --executor threads
modelly sensitivity study.toml --output ranking.csv
```

It prints the ranking. Exit status: 0 when the analysis finished, 1 when a model run failed,
2 for a bad command line or spec. `python -m modelly.sensitivity` is the same command.
