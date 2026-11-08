# Emulate

`modelly.emulate` fits emulators to a model’s runs, chooses runs by active learning and rules out parameters by history matching. How to use it is in [Emulators](https://remipelloux.github.io/Modelly/dev/emulators.html).

## Emulators

What every emulator shares: named outputs, predictions on the unit cube, accuracy, data.

An emulator is fitted to `units[point, dimension]` (points of the unit cube of a `ScenarioSpace`, as designs draw them) and `values[point, output]`. `predict` returns the mean and standard deviation of every output; `select` keeps one output, and an emulator with one output and its `space` stands in for the model in `modelly.sensitivity`. [`Emulator.from_results()`](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#modelly.emulate.base.Emulator.from_results) trains one on the runs of an `Experiment`.

#### `output_names(count: int, names: Sequence[str] | None = None) → list[str]`

`names` checked against `count` outputs, or `y0, y1, ...`.

#### `as_columns(values: ndarray) → ndarray`

`values` as a float array `[point, output]` (one column for a 1-d array).

#### `class Emulator`

Base class: a fit of several outputs over the unit cube.

Subclasses implement `fit`, `predict` and `_subset`.

**Variables:**

- **names** ([*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*]*) – the outputs, in column order.
- **space** ([*modelly.experiments.space.ScenarioSpace*](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.space.ScenarioSpace)* | **None*) – the space whose unit cube the inputs are (`None` if not known).

#### `classmethod fit(units: ndarray, values: ndarray, names: Sequence[str] | None = None, **options: Any) → Emulator`

Fit to `units[point, dimension]` and `values[point, output]`.

#### `predict(units: ndarray) → tuple[ndarray, ndarray]`

The predicted mean and standard deviation, each `[point, output]`.

#### `select(name: str) → Emulator`

The emulator of one output (for the sensitivity methods).

#### `predict_unit(units: ndarray) → ndarray`

The predicted mean of the only output (the sensitivity methods call this).

#### `score(units: ndarray, values: ndarray) → dict[str, float]`

The normalised root-mean-square error of every output on test data.

The error is divided by the test values’ standard deviation: 0 is perfect, 1 is no better than predicting their mean.

#### `classmethod from_results(results: Results, space: ScenarioSpace, outputs: Mapping[str, str | Callable[[ndarray], float]] | Sequence[str], **options: Any) → Emulator`

Fit to an experiment’s runs: one point per design point, replicates averaged.

`outputs` lists recorded outputs (each run’s last value) or maps each to a statistic of its series (`"last"`, `"max"`, `"mean"`… or a function); `options` go to `fit`.

#### `unit_of(space: ScenarioSpace, params: Mapping[str, Any]) → ndarray`

The unit-cube position of `params`: the inverse of `space.point`.

A level of an integer range or a choice maps to the centre of its share.

#### `reducer(statistic: str | Callable[[ndarray], float]) → Callable[[ndarray], float]`

The function a statistic names (`"last"`, `"max"`…), or the function given.

#### `training_data(results: Results, space: ScenarioSpace, outputs: Mapping[str, str | Callable[[ndarray], float]] | Sequence[str]) → tuple[ndarray, ndarray]`

`(units, values)` of an experiment’s runs, one row per design point.

A Gaussian-process emulator: one process per output, on the unit cube.

Each output gets the Gaussian process of [`modelly.calibrate.gp`](https://remipelloux.github.io/Modelly/dev/apis/calibrate.html#module-modelly.calibrate.gp) (squared exponential kernel, one length scale per input, a fitted noise term), fitted with restarts by default. Besides the mean and standard deviation it gives the predictive covariance and the variance after more runs (`condition`), which the active-learning designs of [`modelly.emulate.active`](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#module-modelly.emulate.active) use.

Example

```default
>>> import numpy as np
>>> units = np.linspace(0, 1, 9)[:, None]
>>> emulator = GaussianEmulator.fit(units, np.sin(6 * units[:, 0]))
>>> mean, sd = emulator.predict([[0.5]])
>>> bool(abs(mean[0, 0] - np.sin(3.0)) < 0.05)
True
```

#### `class GaussianEmulator(processes: list[GaussianProcess], names: list[str], space: ScenarioSpace | None = None)`

Independent Gaussian processes, one per output.

**Variables:**

- **processes** ([*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*modelly.calibrate.gp.GaussianProcess*](https://remipelloux.github.io/Modelly/dev/apis/calibrate.html#modelly.calibrate.gp.GaussianProcess)*]*) – the fitted processes, one per output.
- **names** ([*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*]*) – the outputs.
- **space** ([*modelly.experiments.space.ScenarioSpace*](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.space.ScenarioSpace)* | **None*) – the space whose unit cube the inputs are, if known.

#### `classmethod fit(units: ndarray, values: ndarray, names: Sequence[str] | None = None, *, space: ScenarioSpace | None = None, restarts: bool = True) → GaussianEmulator`

Fit one process per column of `values`; `restarts` as in `GaussianProcess.fit`.

#### `predict(units: ndarray) → tuple[ndarray, ndarray]`

The mean and standard deviation of the fitted functions, `[point, output]`.

#### `covariance(a: ndarray, b: ndarray) → ndarray`

The predictive covariance `[output, row of a, row of b]`.

#### `property noise_variance: ndarray`

The fitted noise variance of every output (run-to-run scatter).

#### `condition(units: ndarray) → GaussianEmulator`

The emulator as if `units` had been run and returned the predicted mean.

The hyperparameters are kept, so the standard deviations are those the emulator would have after the runs: how a batch is chosen.

A small neural emulator: an ensemble of multilayer perceptrons, numpy only.

Each member is a fully connected network (`tanh` hidden layers, a linear output per emulated output) trained on the standardised data by full-batch Adam on the mean squared error plus a weight penalty. The members differ only in their random initial weights; the ensemble’s mean is the prediction and the spread between members its standard deviation (a “deep ensemble”, Lakshminarayanan, Pritzel and Blundell 2017). It needs no deep-learning library and suits a few hundred to a few thousand runs, where a Gaussian process gets slow; with few runs the Gaussian process is usually more accurate.

Every weight is drawn from `settings.seed`: the same data and seed give the same emulator.

Example

```default
>>> import numpy as np
>>> units = np.linspace(0, 1, 40)[:, None]
>>> emulator = NeuralEmulator.fit(units, units[:, 0] ** 2)
>>> bool(abs(emulator.predict([[0.5]])[0][0, 0] - 0.25) < 0.05)
True
```

#### `class NeuralSettings(hidden: tuple[int, ...] = (32, 32), members: int = 5, epochs: int = 2000, learning_rate: float = 0.01, penalty: float = 1e-05, seed: int = 0)`

How the ensemble is built and trained.

**Parameters:**

- **hidden** – the width of each hidden layer.
- **members** – the number of networks in the ensemble.
- **epochs** – full-batch Adam steps per network.
- **learning_rate** – Adam’s step size.
- **penalty** – the weight of the squared-weights penalty.
- **seed** – the root of every initial weight.

#### `class NeuralEmulator(members: list[list[tuple[ndarray, ndarray]]], names: list[str], center: ndarray, scale: ndarray, space: ScenarioSpace | None = None)`

An ensemble of small networks over the unit cube.

**Variables:**

- **members** ([*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[**numpy.ndarray**, **numpy.ndarray**]**]**]*) – every network’s layers.
- **names** ([*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*]*) – the outputs.
- **center** (*numpy.ndarray*) – the outputs’ training means.
- **scale** (*numpy.ndarray*) – the outputs’ training standard deviations.
- **space** ([*modelly.experiments.space.ScenarioSpace*](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.space.ScenarioSpace)* | **None*) – the space whose unit cube the inputs are, if known.

#### `classmethod fit(units: ndarray, values: ndarray, names: Sequence[str] | None = None, *, space: ScenarioSpace | None = None, settings: NeuralSettings | None = None) → NeuralEmulator`

Train `settings.members` networks on `units` and the columns of `values`.

#### `predict(units: ndarray) → tuple[ndarray, ndarray]`

The ensemble’s mean and spread (standard deviation), `[point, output]`.

## Runs

What an emulator learns: the outputs of a model (or a function) at points of a space.

A [`Simulation`](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#modelly.emulate.simulation.Simulation) turns rows of the unit cube of a `ScenarioSpace` into `values[point, output]`:

- a Model class (or `"module:Class"` reference) is run through the experiment executors ([`modelly.calibrate.simulator`](https://remipelloux.github.io/Modelly/dev/apis/calibrate.html#module-modelly.calibrate.simulator)), each batch of runs written to a Parquet store; every output is something the model records each step, reduced to one number per run by a statistic and averaged over replicates:

```default
Simulation(Epidemic, space, {"peak": ("infected", "max"), "size": "recovered"})
```

- a plain function is called with the parameters as keyword arguments and returns one number, a sequence, or a mapping `{output: value}`.

Run seeds follow the experiment discipline: a batch’s seeds depend only on the simulation’s `seed` and the batch key, never on the executor. With `common=True` every point runs with the same replicate seeds (common random numbers), which makes a stochastic model’s output a smoother function of its parameters.

#### `class Simulation(model: Any, space: ScenarioSpace, outputs: Mapping[str, ~typing.Any] | ~collections.abc.Sequence[str] | None=None, seed: int = 0, steps: int = 100, replicates: int = 1, common: bool = False, store: str | Path | None = None, executor: Any = 'serial', max_parallel: int | None = None, options: Mapping[str, ~typing.Any]=<factory>)`

A model or function and the outputs an emulator learns.

**Parameters:**

- **model** – a Model class or reference, or a function of the parameters.
- **space** – the parameter space; its ranges and choices are the inputs.
- **outputs** – for a model, a list of recorded outputs (each run’s last value) or `{name: output}` / `{name: (output, statistic)}`, the statistic one of `"last"`, `"max"`, `"min"`, `"mean"`, `"sum"` or a function of the series; for a function, its outputs’ names (one output named `"output"` by default).
- **seed** – the root of every run’s seed.
- **steps** – steps per run (models only).
- **replicates** – runs per point, averaged (models only).
- **common** – run every point with the same replicate seeds (models only).
- **store** – the folder of the runs (a temporary one by default).
- **executor** – where the runs execute (any experiment executor).
- **max_parallel** – the most runs at once.
- **options** – the executor’s options.

`with simulation:` keeps one pool of workers for every batch run inside the block (`"processes"` otherwise starts one per batch).

#### `property names: list[str]`

The outputs, in column order.

#### `evaluate(units: ndarray, key: Sequence[int]) → ndarray`

`values[point, output]` at the rows of `units`; `key` names the batch.

## Active learning

Active learning: choose the next runs where the emulator is least certain.

An [`ActiveLearning`](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#modelly.emulate.active.ActiveLearning) design starts from a small Latin hypercube, fits an emulator, and then, batch after batch, runs the candidate points the emulator would learn most from, refitting after every batch:

- `criterion="ivr"` (the default): the largest integrated variance reduction, the drop in predictive variance averaged over the whole space that running the point would bring (Cohn 1996’s ALC; Sacks, Welch, Mitchell and Wynn 1989), the error measure an emulator is judged by;
- `criterion="variance"`: the largest predictive variance (MacKay 1992’s ALM): cheaper, but it favours the edges of the space, more so in more dimensions.

A batch of several runs is chosen greedily: after each pick the emulator is conditioned on it (its variance becomes what it would be after the run, the “kriging believer”), so the batch spreads out instead of piling up where the variance was largest. The batch then runs at once on the simulation’s executor. With several outputs, the criteria add the outputs’ variances, each relative to its spread in the runs so far.

Every random draw (the first design, the candidates, the reference points) comes from the simulation’s seed: the same seed chooses the same runs.

Example

```default
>>> import math
>>> from modelly.experiments import ScenarioSpace
>>> space = ScenarioSpace(x=(0.0, 1.0), y=(0.0, 1.0))
>>> simulation = Simulation(lambda x, y: math.sin(6 * x) + y, space, seed=1)
>>> design = ActiveLearning(simulation, ActiveSettings(batch=2)).run(runs=14)
>>> len(design.units)
14
```

#### `class ActiveSettings(initial: int | None = None, batch: int = 1, criterion: str = 'ivr', candidates: int = 1000, references: int = 300, emulator: type[Emulator] = <class 'modelly.emulate.gaussian.GaussianEmulator'>, options: Mapping[str, ~typing.Any]=<factory>)`

How an active-learning design chooses its runs.

**Parameters:**

- **initial** – runs of the first Latin hypercube (`2 * dimensions + 2` by default).
- **batch** – runs chosen and run together at each iteration.
- **criterion** – `"ivr"` (integrated variance reduction) or `"variance"`.
- **candidates** – random points scored at each iteration.
- **references** – points the integrated variance is averaged over (`"ivr"`).
- **emulator** – the emulator class (a batch needs `condition`, as [`GaussianEmulator`](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#modelly.emulate.gaussian.GaussianEmulator) has).
- **options** – keyword arguments of the emulator’s `fit`.

#### `emulator`

alias of [`GaussianEmulator`](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#modelly.emulate.gaussian.GaussianEmulator)

#### `class ActiveDesign(simulation: Simulation, units: ndarray, values: ndarray, iterations: ndarray, emulator: Emulator)`

The runs an active-learning design chose, and the emulator fitted to them.

**Variables:**

- **simulation** ([*modelly.emulate.simulation.Simulation*](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#modelly.emulate.simulation.Simulation)) – what was run.
- **units** (*numpy.ndarray*) – the runs’ points of the unit cube, in the order they ran.
- **values** (*numpy.ndarray*) – their outputs `[run, output]`.
- **iterations** (*numpy.ndarray*) – the iteration of each run (0 for the first design).
- **emulator** ([*modelly.emulate.base.Emulator*](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#modelly.emulate.base.Emulator)) – the emulator fitted to every run.

#### `points() → list[dict[str, Any]]`

The parameters of every run, in the order they ran.

#### `design() → Custom`

The runs as a custom design, to rerun them in an `Experiment`.

#### `frame() → DataFrame`

One row per run: the iteration, the parameters and the outputs.

#### `class ActiveLearning(simulation: Simulation, settings: ActiveSettings | None = None)`

An active-learning design over a simulation (see the module docstring).

`run(runs)` can be called again with a larger `runs` to go on.

Nothing runs before `run`.

#### `run(runs: int) → ActiveDesign`

Run until `runs` runs are done; the design and its emulator.

#### `fit() → Emulator`

The emulator fitted to every run so far.

## History matching

History matching: rule out, wave by wave, the parameters that cannot match the data.

For an observed value `z` of an output, the implausibility of a point `x` of the parameter space is:

```default
I(x) = |z - E[f(x)]| / sqrt(Var[f(x)] + Var_obs + Var_discrepancy)
```

where `E[f(x)]` and `Var[f(x)]` are an emulator’s prediction of the model’s output, `Var_obs` the observation error and `Var_discrepancy` the model discrepancy (what even the best parameters miss, the run-to-run scatter of a stochastic model included). With several outputs a point’s implausibility is the largest of theirs (or, with `rank=2`, the second largest). A point with `I(x) > cutoff` (3, by Pukelsheim’s three-sigma rule) is implausible.

A [`HistoryMatch`](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#modelly.emulate.history.HistoryMatch) runs waves (Vernon, Goldstein and Bower 2010; Andrianakis et al. 2015). Wave 1 spreads `runs` runs over the whole space, fits an emulator and rules out the implausible part. Each later wave spreads its runs over the space not yet ruled out, refits the emulators on the runs inside it (more accurate there, as the region is smaller) and rules out more. The space not ruled out yet, NROY, is tracked on a fixed random sample of `candidates` points of the space, so its volume is the share of the sample left.

Example

```default
>>> from modelly.experiments import ScenarioSpace
>>> space = ScenarioSpace(a=(0.0, 1.0), b=(0.0, 1.0))
>>> simulation = Simulation(lambda a, b: [a + b, a - b], space, ["sum", "diff"])
>>> observed = [Observation("sum", 1.0, 1e-4), Observation("diff", 0.2, 1e-4)]
>>> result = HistoryMatch(simulation, observed).run(waves=2, runs=12)
>>> bool(result.volumes[-1] < 0.1 and result.contains({"a": 0.6, "b": 0.4}))
True
```

#### `class Observation(name: str, value: float, variance: float, discrepancy: float = 0.0)`

One observed output and its uncertainty.

**Parameters:**

- **name** – the simulation output it observes.
- **value** – the observed value `z`.
- **variance** – the observation error variance.
- **discrepancy** – the model discrepancy variance.

#### `implausibility(mean: ndarray, sd: ndarray, observations: Sequence[Observation]) → ndarray`

`I[point, output]` from an emulator’s `mean` and `sd` (columns as observations).

#### `class MatchSettings(cutoff: float = 3.0, rank: int = 1, candidates: int = 20000, emulator: type[Emulator] = <class 'modelly.emulate.gaussian.GaussianEmulator'>, options: Mapping[str, ~typing.Any]=<factory>)`

How the waves rule out space.

**Parameters:**

- **cutoff** – the implausibility above which a point is ruled out.
- **rank** – combine the outputs by their largest implausibility (1) or the `rank`-th largest (2 tolerates one badly matched output).
- **candidates** – the random points of the space NROY is tracked on.
- **emulator** – the emulator class refitted at every wave.
- **options** – keyword arguments of the emulator’s `fit`.

#### `emulator`

alias of [`GaussianEmulator`](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#modelly.emulate.gaussian.GaussianEmulator)

#### `class Wave(number: int, units: ndarray, values: ndarray, training: int, emulator: Emulator, volume: float)`

One wave: its runs, the emulator fitted to the runs inside its region, and NROY.

**Variables:**

- **number** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – 1 for the first wave.
- **units** (*numpy.ndarray*) – the wave’s runs, as points of the unit cube.
- **values** (*numpy.ndarray*) – their outputs `[run, output]`.
- **training** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – how many runs (this wave’s and earlier ones in its region) fitted the emulator.
- **emulator** ([*modelly.emulate.base.Emulator*](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#modelly.emulate.base.Emulator)) – the wave’s emulator of the observed outputs.
- **volume** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the share of the space not ruled out after this wave.

#### `class MatchResult(simulation: Simulation, observations: list[Observation], settings: MatchSettings, waves: list[Wave], candidates: ndarray, alive: ndarray)`

The waves of a history match and the space they did not rule out.

**Variables:**

- **simulation** ([*modelly.emulate.simulation.Simulation*](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#modelly.emulate.simulation.Simulation)) – what was run.
- **observations** ([*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*modelly.emulate.history.Observation*](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#modelly.emulate.history.Observation)*]*) – what was matched.
- **settings** ([*modelly.emulate.history.MatchSettings*](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#modelly.emulate.history.MatchSettings)) – how.
- **waves** ([*list*](https://docs.python.org/3/builtins/stdtypes.html#list)*[*[*modelly.emulate.history.Wave*](https://remipelloux.github.io/Modelly/dev/apis/emulate.html#modelly.emulate.history.Wave)*]*) – every wave, the first first.
- **candidates** (*numpy.ndarray*) – the sample of the space NROY is tracked on.
- **alive** (*numpy.ndarray*) – which candidates are not ruled out.

#### `property volumes: list[float]`

The share of the space not ruled out after each wave.

#### `implausibility(units: ndarray) → ndarray`

The combined implausibility `[wave, point]` of each wave’s emulator.

#### `wave_implausibility(wave: Wave, units: ndarray) → ndarray`

One wave’s combined implausibility at `units`: the `rank`-th largest output’s.

#### `nonimplausible(units: ndarray) → ndarray`

Whether each point is below the cutoff under every wave.

#### `contains(params: Mapping[str, Any]) → bool`

Whether the parameters `params` are not ruled out.

#### `samples() → DataFrame`

The candidates not ruled out, as parameters: a sample of NROY.

#### `table() → DataFrame`

One row per wave: its runs, its training runs and the volume left.

#### `maximin(region: ndarray, count: int, rng: Generator) → ndarray`

`count` points of `region` chosen greedily far from each other (all if fewer).

#### `class HistoryMatch(simulation: Simulation, observations: Sequence[Observation], settings: MatchSettings | None = None)`

History matching of a simulation to observations (see the module docstring).

`run(waves)` can be called again with more waves to go on.

Check the observations name outputs; nothing runs before `run`.

#### `run(waves: int, runs: int = 40) → MatchResult`

Run `waves` more waves of `runs` runs each; stop early if NROY is empty.
