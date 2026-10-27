# Emulators, active learning and history matching

A model that takes minutes per run cannot be run a hundred thousand times for a calibration
or a sensitivity analysis. An **emulator** is a fast statistical stand-in fitted to a few
dozen or a few hundred runs, which also says how unsure it is. `modelly.emulate` fits them,
chooses where to run next (**active learning**) and rules out the parameters that cannot
reproduce the data (**history matching**).

| Name | What it does |
|---|---|
| `GaussianEmulator` | one Gaussian process per output: mean, standard deviation, covariance |
| `NeuralEmulator` | an ensemble of small numpy networks, for more runs than a Gaussian process handles |
| `Simulation` | runs a model (through the [experiment executors](experiments.md)) or a function at chosen points |
| `ActiveLearning` | adds runs where the emulator is least certain, in batches |
| `HistoryMatch` | waves of runs that rule out implausible parameters |

Model runs go to a Parquet store, so models need the `experiments` extra
(`pip install "modelly-abm[experiments]"`); functions do not. Nothing else is needed: the
Gaussian process is the one of `modelly.calibrate` (numpy and scipy) and the networks are
plain numpy.

## Emulators

Every emulator is fitted to points of the unit cube of a `ScenarioSpace` (one coordinate per
range or choice, as designs draw them) and to the outputs there, one column per output:

```python
import numpy as np

from modelly.emulate import GaussianEmulator

units = np.random.default_rng(1).random((30, 2))
values = np.column_stack([np.sin(5 * units[:, 0]), units[:, 0] * units[:, 1]])
emulator = GaussianEmulator.fit(units, values, ["wave", "product"])
mean, sd = emulator.predict([[0.5, 0.5]])  # both [point, output]
emulator.score(test_units, test_values)  # normalised RMSE per output: 0 is perfect
```

Each output gets its own process: a squared-exponential kernel with one length scale per
input and a fitted noise term (the run-to-run scatter of a stochastic model). The
hyperparameters are fitted from five starting points (`restarts=True`, the default here),
because from a single start the likelihood search often ends at a fit that calls everything
noise. `covariance(a, b)` gives the predictive covariance and `condition(units)` the emulator
as if those points had been run, which is what batch selection needs.

`NeuralEmulator.fit(units, values, settings=NeuralSettings(...))` trains an ensemble of
`members` fully connected networks (`tanh` hidden layers, full-batch Adam); the mean of the
members is the prediction and their spread the standard deviation (a "deep ensemble",
Lakshminarayanan et al. 2017). With a few dozen runs the Gaussian process is usually more
accurate; the networks scale to thousands of runs, where the process's cubic cost does not.
Every weight comes from `settings.seed`.

### From an experiment's results

An experiment already in a store trains an emulator directly: one point per design point,
replicates averaged, each output reduced by a statistic of its series:

```python
from modelly.experiments import Experiment, ScenarioSpace, designs

experiment = Experiment(model=Epidemic, space=space, design=designs.latin_hypercube(80),
                        replicates=4, steps=120, outputs=["infected"], store="runs/sir")
experiment.run(executor="processes")
emulator = GaussianEmulator.from_results(experiment.results(), space, {"infected": "max"})
```

### In a sensitivity analysis

An emulator of one output whose `space` is set (`from_results` and the designs below set
it) stands in for the model in `oat`, `morris`, `sobol` and `pawn`, which then cost no runs:

```python
from modelly.sensitivity import sobol

sobol(emulator.select("infected"), space, samples=8192)
```

`modelly.sensitivity.emulate` remains the one-call way to fit a Latin-hypercube emulator for
a sensitivity analysis.

## Simulations

A `Simulation` names what is run and what is emulated:

```python
from modelly.emulate import Simulation

simulation = Simulation(
    AgeSEIR,
    space,
    {"peak": ("mymodel:infectious", "max"), "size": "mymodel:recovered"},
    steps=150,
    replicates=1,
    seed=1,
    executor="processes",
)
```

Each output is something the model records every step (an attribute, a method or a
module-level function of the model, as for an `Experiment`) and a statistic that reduces a
run's series to one number: `"last"` (the default), `"max"`, `"min"`, `"mean"`, `"sum"` or a
function. A plain function of the parameters can stand in for the model; it returns a number,
a sequence or a mapping. `common=True` runs every point with the same replicate seeds
(common random numbers): the output becomes a smoother function of the parameters, which an
emulator learns from fewer runs.

## Active learning

```python
from modelly.emulate import ActiveLearning, ActiveSettings

design = ActiveLearning(simulation, ActiveSettings(batch=4)).run(runs=40)
design.emulator  # fitted to all 40 runs
design.frame()  # iteration, parameters and outputs of every run
design.design()  # the runs as a custom design, to rerun them in an Experiment
```

The design starts from a Latin hypercube of `2 d + 2` runs (`initial`), then at each
iteration scores `candidates` random points and runs the best `batch` of them at once on the
simulation's executor, refitting the emulator after every batch. `run` can be called again
with more runs to go on.

| `criterion` | Picks the point that |
|---|---|
| `"ivr"` (default) | most reduces the predictive variance averaged over `references` points of the space: the integrated variance reduction (Cohn 1996; Sacks et al. 1989) |
| `"variance"` | has the largest predictive variance (MacKay 1992): cheaper, but drawn to the edges and corners, more so in more dimensions |

A batch is chosen greedily: after each pick the emulator is conditioned on it (the
"kriging believer"), so the variance there drops and the next pick goes elsewhere. With
several outputs the criteria add the outputs' variances, each relative to its spread.

### How many runs it saves

The benchmark (`benchmarks/emulate/active_vs_lhs.py`, protocol in
`tests/emulate/test_active.py`): accuracy is the normalised RMSE on 500 random test points,
a Latin hypercube of `n` runs scores the median of three seeds, active learning adds four runs
per iteration, and the factor is the hypercube runs needed for the active design's accuracy,
divided by the active runs. The 1.4.0 roadmap asked for a factor of 2.

Factor of runs saved (hypercube runs for the same error / active runs), measured on one
machine with `OPENBLAS_NUM_THREADS=1`; "> 2.4" means the active design beat every hypercube
measured, up to twice its runs:

| Active runs | Branin, `ivr` | Branin, `variance` | Ishigami, `ivr` | Ishigami, `variance` | Bass diffusion, `ivr` |
|---|---|---|---|---|---|
| 10 | 1.13 | 1.57 | 1.00 | 1.00 | 1.64 |
| 20 | 1.20 | 1.18 | 0.79 | 1.82 | **2.64** |
| 30 | 1.38 | 1.45 | 0.95 | 0.33 | 1.33 |
| 40 | 1.43 | 1.28 | 1.13 | 0.25 | **2.67** |
| 50 | 1.23 | 1.29 | 0.97 | 0.20 | **> 2.4** |
| 60 | 1.15 | 1.21 | 1.34 | 0.40 | **> 2.4** |
| 70 | 1.15 | 1.40 | 1.19 | 0.33 | |
| 80 | **> 1.9** | 1.83 | 1.11 | 1.01 | |
| 100 | | | 1.41 | 0.88 | |

Branin is the two-dimensional test function of Dixon and Szego (1978), Ishigami the
three-dimensional one of the sensitivity tests, and Bass diffusion the zoo model
(`bass_diffusion`, 20,000 households, well mixed): the share adopted after four years over
the innovation rate (0.005 to 0.05) and the imitation rate (0.1 to 0.8), common random
numbers for every run. Errors at 80 Branin runs and at 50 or more Bass runs are at the
floor the hypercubes reach too (rounding and run-to-run scatter), so the factor there is a
bound, not a measurement.

So the roadmap's factor of 2 holds on the zoo model at most budgets (not at 30 runs), and
not on the two analytic functions, where integrated variance reduction needs 12 to 30 %
fewer runs than a hypercube on Branin below 80 runs and at most 29 % fewer on Ishigami, with
budgets where it needs as many or more. A
Gaussian process's variance does not depend on the outputs, only on where the runs are and
on the fitted length scales, so on a function that varies evenly over the space an active
design is mostly a well-spread design, and a Latin hypercube already is one. The pure
variance criterion does worse than a hypercube on Ishigami: in three dimensions it spends its
runs on the corners. The tests pin what was measured: 40 active runs match a hypercube of 50
on Branin, and 20 match one of 40 on Bass diffusion (10,000 households there, to keep the
test fast).

## History matching

History matching asks the opposite question to calibration: not "which parameters fit best"
but "which parameters cannot possibly fit". For an observed value `z` of an output, the
implausibility of a parameter point `x` is

```text
I(x) = |z - E[f(x)]| / sqrt(Var[f(x)] + Var_obs + Var_discrepancy)
```

with `E[f(x)]` and `Var[f(x)]` the emulator's prediction, `Var_obs` the observation error and
`Var_discrepancy` the model discrepancy: what even the best parameters miss, including the
run-to-run scatter of a stochastic model. A point with `I(x) > 3` for some output is ruled out
(three standard deviations, by Pukelsheim's rule, holds for any unimodal distribution).
History matching runs in **waves** (Vernon, Goldstein and Bower 2010; Andrianakis et al. 2015):

1. spread the wave's runs over the space not yet ruled out ("not ruled out yet", NROY);
2. refit the emulators on the runs inside NROY, which are more accurate there than the
   previous wave's because the region is smaller;
3. rule out every point whose implausibility exceeds the cutoff.

NROY is tracked on a fixed random sample of `candidates` points of the space, so its volume is
the share of the sample left, and `samples()` returns the points left as parameters.

### A worked example: an age-structured SEIR epidemic

The zoo's `age_seir` model with its default parameters (`beta=0.035`, `incubation=0.25`,
`recovery=0.2`) plays the truth. One run of it gives the data: the peak share infectious,
the step of the peak and the share recovered after 150 steps. Can history matching find where
the truth lies in a wide box, without knowing it?

```python
import numpy as np

from modelly.emulate import HistoryMatch, MatchSettings, Observation, Simulation
from modelly.experiments import ScenarioSpace
from modelly.zoo.age_seir.model import AgeSEIR, State


def infectious(model):
    return float(model.counts()[:, State.I].sum() / model.sizes.sum())


def recovered(model):
    return float(model.counts()[:, State.R].sum() / model.sizes.sum())


def peak_step(series):
    return float(np.argmax(series))


outputs = {
    "peak": ("seir_outputs:infectious", "max"),
    "timing": ("seir_outputs:infectious", peak_step),
    "size": ("seir_outputs:recovered", "last"),
}
observations = [
    # value from one run at the truth; 5 % observation error; scatter of 8 runs there
    Observation("peak", 0.09225, (0.05 * 0.09225) ** 2, 3.1e-6),
    Observation("timing", 80.0, (0.05 * 80.0) ** 2, 6.0),
    Observation("size", 0.77659, (0.05 * 0.77659) ** 2, 1.5e-6),
]
space = ScenarioSpace(beta=(0.01, 0.08), incubation=(0.1, 0.6), recovery=(0.1, 0.5))
simulation = Simulation(AgeSEIR, space, outputs, steps=150, seed=1)
match = HistoryMatch(simulation, observations, MatchSettings(candidates=10_000))
result = match.run(waves=4, runs=20)
print(result.table())
result.contains({"beta": 0.035, "incubation": 0.25, "recovery": 0.2})  # True
```

(the three functions live in an importable module, here `seir_outputs.py`, so that process
workers find them.)

```text
      runs  training  volume
wave
1       20        20  0.1705
2       20        20  0.0444
3       20        23  0.0307
4       20        26  0.0246
```

Eighty runs rule out 97.5 % of the box, and the truth is never ruled out (its largest
implausibility over the waves is 2.2). What is left is the shape history matching is known
for: a ridge, not a point. The peak and the final size pin down the reproduction number
`beta / recovery` (times the contact matrix's spectral radius), so `beta` and `recovery` are
tied together, while the incubation rate only moves the peak's timing, which the data know to
±5 steps; NROY keeps incubation rates from 0.10 to 0.59. A calibration (`modelly.calibrate`)
started inside NROY then needs far fewer runs. `tests/emulate/test_history.py` runs this
example and checks that each wave shrinks NROY, that the truth is inside it after every wave,
and that `MODELLY_PURE_PYTHON=1` rules out exactly the same points.

`MatchSettings(rank=2)` combines the outputs by their second-largest implausibility instead of
the largest, which tolerates one badly emulated or badly modelled output (Vernon et al.
2010). `run(waves)` can be called again to add waves; it stops early when NROY is empty, which
means no parameter in the box reproduces the data within the stated uncertainties: the model,
the box or the discrepancy is wrong.

## Seeds and executors

Every random draw (the first design, the candidates, the reference points, the NROY sample,
the maximin start of each wave, the networks' weights) comes from the simulation's `seed`, and
the runs' seeds follow the experiment discipline, so the same seed gives the same runs,
emulators and waves on every executor, with the compiled core or with
`MODELLY_PURE_PYTHON=1`.

Small matrix operations are slow with a multi-threaded BLAS on a busy machine; when many
emulators are fitted in a row (active learning, the benchmark), `OPENBLAS_NUM_THREADS=1`
(or `OMP_NUM_THREADS=1`) can be an order of magnitude faster.

## References

- Andrianakis, I. et al. (2015). Bayesian history matching of complex infectious disease
  models using emulation: a tutorial and a case study on HIV in Uganda. PLoS Computational
  Biology, 11(1), e1003968.
- Cohn, D. A. (1996). Neural network exploration using optimal experiment design. Neural
  Networks, 9(6), 1071-1083.
- Lakshminarayanan, B., Pritzel, A. and Blundell, C. (2017). Simple and scalable predictive
  uncertainty estimation using deep ensembles. NeurIPS 30.
- MacKay, D. J. C. (1992). Information-based objective functions for active data selection.
  Neural Computation, 4(4), 590-604.
- Sacks, J., Welch, W. J., Mitchell, T. J. and Wynn, H. P. (1989). Design and analysis of
  computer experiments. Statistical Science, 4(4), 409-423.
- Vernon, I., Goldstein, M. and Bower, R. G. (2010). Galaxy formation: a Bayesian uncertainty
  analysis. Bayesian Analysis, 5(4), 619-669.
