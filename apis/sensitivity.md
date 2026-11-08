# Sensitivity

`modelly.sensitivity` ranks parameters by their influence. How to use it is in [Sensitivity analysis](https://remipelloux.github.io/Modelly/sensitivity.html).

## Methods

Screening: one-at-a-time sweeps and Morris elementary effects.

Example

```default
>>> from modelly.experiments import ScenarioSpace
>>> space = ScenarioSpace(a=(0.0, 1.0), b=(0.0, 1.0))
>>> screen = morris(lambda a, b: 4 * a + b, space, trajectories=4, seed=1)
>>> list(screen.ranking().index)
['a', 'b']
```

#### `oat(model: Any, space: ScenarioSpace, output: Any = None, *, levels: int = 5, **settings: Any) → OATResult`

Vary each parameter alone over `levels` values, the others at their midpoint.

`effect` is the output’s range along a parameter’s sweep. `settings` are the [`Study`](https://remipelloux.github.io/Modelly/apis/sensitivity.html#modelly.sensitivity.study.Study) fields (seed, steps, replicates, statistic, store, executor, max_parallel, options).

#### `morris_design(dimensions: int, count: int, levels: int, rng: Generator) → tuple[ndarray, ndarray, ndarray]`

Morris trajectories on a `levels` grid.

Returns the points `[trajectory, step, dimension]` (`dimensions + 1` steps), the factor each step moves `[trajectory, step]` and its signed size `[trajectory, step]`.

#### `morris(model: Any, space: ScenarioSpace, output: Any = None, *, trajectories: int = 10, levels: int = 4, **settings: Any) → MorrisResult`

Morris elementary effects: `mu`, `mu_star` (ranking) and `sigma` per parameter.

`trajectories` random trajectories on a `levels` grid, drawn from the stream `(DESIGN, MORRIS_KEY)` of the seed: `trajectories * (parameters + 1)` evaluations. `settings` are the [`Study`](https://remipelloux.github.io/Modelly/apis/sensitivity.html#modelly.sensitivity.study.Study) fields.

Variance-based sensitivity: first-order and total Sobol indices.

Saltelli sampling: two independent matrices `A` and `B` of `samples` rows each come from one scrambled Sobol sequence of twice the dimension (`scipy.stats.qmc`, scrambled from the seed), and `AB_i` is `A` with column `i` taken from `B`: `samples * (parameters + 2)` evaluations.

Estimators (Saltelli et al., 2010), with `V` the variance of `f(A)` and `f(B)`:

estimator

S1

ST

jansen

(V - mean((f(B) - f(AB_i))**2) / 2) / V

mean((f(A) - f(AB_i))**2) / 2 / V

saltelli

mean(f(B) * (f(AB_i) - f(A))) / V

mean(f(A) * (f(A) - f(AB_i))) / V

Confidence intervals come from resampling the rows `bootstrap` times (the stream `(BOOTSTRAP, SOBOL_KEY)` of the seed) and taking percentiles.

#### `saltelli_sample(dimensions: int, samples: int, rng: Generator) → ndarray`

The points `[A; B; AB_1; ...; AB_d]` in the unit cube.

#### `indices(f_a: ndarray, f_b: ndarray, f_ab: ndarray, estimator: str) → tuple[ndarray, ndarray]`

S1 and ST from `f(A)`, `f(B)` and `f(AB)[parameter, row]`.

#### `sobol(model: Any, space: ScenarioSpace, output: Any = None, *, samples: int = 1024, bootstrap: int = 200, confidence: float = 0.95, estimator: str = 'jansen', **settings: Any) → SobolResult`

First-order (`S1`) and total (`ST`) Sobol indices with bootstrap intervals.

`samples` should be a power of two. `settings` are the [`Study`](https://remipelloux.github.io/Modelly/apis/sensitivity.html#modelly.sensitivity.study.Study) fields (seed, steps, replicates, statistic, store, executor, max_parallel, options).

PAWN: moment-independent sensitivity from output distributions (Pianosi and Wagener, 2015).

One Latin-hypercube sample of `samples` points is evaluated. For each parameter its range is cut into `slices` equal-count slices; in each slice the distribution of the output is compared with the unconditional one by the Kolmogorov-Smirnov statistic (the largest gap between the two CDFs). A parameter’s index summarises its slices’ statistics (`median`, `mean`, `max`); 0 means the output’s distribution does not change with it. Suits skewed or multi-modal outputs, where variance-based indices mislead.

#### `ks_statistics(column: ndarray, output: ndarray, slices: int) → ndarray`

The KS statistic of each slice of `column` against the whole `output`.

#### `pawn(model: Any, space: ScenarioSpace, output: Any = None, *, samples: int = 500, slices: int = 10, summary: str = 'median', **settings: Any) → SensitivityResult`

PAWN indices (`median`, `mean` and `max` KS statistic) per parameter.

`summary` picks the column `ranking` sorts by. `settings` are the [`Study`](https://remipelloux.github.io/Modelly/apis/sensitivity.html#modelly.sensitivity.study.Study) fields.

A Gaussian-process emulator: analyse an expensive model from a few hundred runs.

`emulate` runs the model at a Latin hypercube of `samples` points and fits the basic Gaussian process of [`modelly.calibrate.gp`](https://remipelloux.github.io/Modelly/apis/calibrate.html#module-modelly.calibrate.gp) to the output. The returned [`Emulator`](https://remipelloux.github.io/Modelly/apis/sensitivity.html#modelly.sensitivity.emulator.Emulator) stands in for the model in `oat`, `morris`, `sobol` and `pawn`, which then cost no further runs:

```default
surrogate = emulate(Epidemic, space, "peak", samples=200, steps=120)
print(surrogate.r2)            # leave-one-out accuracy, near 1 is good
sobol(surrogate, space, samples=4096)
```

#### `class Emulator(space: ScenarioSpace, process: GaussianProcess, units: ndarray, values: ndarray, r2: float)`

A fitted Gaussian process over the unit cube of `space`.

**Variables:**

- **space** ([*modelly.experiments.space.ScenarioSpace*](https://remipelloux.github.io/Modelly/apis/experiments.html#modelly.experiments.space.ScenarioSpace)) – the parameter space it was fitted over.
- **process** ([*modelly.calibrate.gp.GaussianProcess*](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.gp.GaussianProcess)) – the fitted Gaussian process.
- **units** (*numpy.ndarray*) – the training points.
- **values** (*numpy.ndarray*) – the model’s outputs at them.
- **r2** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the share of variance explained on held-out training points.

#### `predict_unit(units: ndarray) → ndarray`

The predicted output at points of the unit cube.

#### `emulate(model: Any, space: ScenarioSpace, output: Any = None, *, samples: int = 200, **settings: Any) → Emulator`

Run `model` at `samples` Latin-hypercube points and fit an Emulator.

`settings` are the [`Study`](https://remipelloux.github.io/Modelly/apis/sensitivity.html#modelly.sensitivity.study.Study) fields.

## Studies and results

What a sensitivity analysis evaluates: a model’s output, a function, or an emulator.

A [`Study`](https://remipelloux.github.io/Modelly/apis/sensitivity.html#modelly.sensitivity.study.Study) turns points of the unit cube (one coordinate per varying parameter of a `ScenarioSpace`) into one number each:

- a Model class (or `"module:Class"` reference) is run through the experiment executors ([`modelly.calibrate.simulator`](https://remipelloux.github.io/Modelly/apis/calibrate.html#module-modelly.calibrate.simulator)); `output` names what it records every step and `statistic` reduces each run’s series to one value (`"last"`, `"max"`, `"min"`, `"mean"`, `"sum"` or a function), averaged over the replicates;
- a plain function is called with the parameters as keyword arguments;
- an [`Emulator`](https://remipelloux.github.io/Modelly/apis/sensitivity.html#modelly.sensitivity.emulator.Emulator) predicts all points at once.

#### `is_model(model: Any) → bool`

Whether `model` is a Model class or a `module:Class` reference to one.

#### `class Study(model: ~typing.Any, space: ~modelly.experiments.space.ScenarioSpace, output: str | ~collections.abc.Callable[[~typing.Any], ~typing.Any] | None = None, seed: int = 0, steps: int = 100, replicates: int = 1, statistic: str | ~collections.abc.Callable[[~numpy.ndarray], float] = 'last', store: str | ~pathlib.Path | None = None, executor: ~typing.Any = 'serial', max_parallel: int | None = None, options: ~collections.abc.Mapping[str, ~typing.Any] = <factory>)`

The quantity analysed and where it is computed.

**Parameters:**

- **model** – a Model class or reference, a function of the parameters, or an Emulator.
- **space** – the parameter space; its ranges and choices are the inputs.
- **output** – for a model, the attribute, method or function of the model to record.
- **seed** – the root of the design, the bootstrap and the runs’ seeds.
- **steps** – steps per run (models only).
- **replicates** – runs per point, averaged (models only).
- **statistic** – how a run’s series becomes one number (models only).
- **store** – the folder of the runs (a temporary one by default).
- **executor** – where the runs execute (any experiment executor).
- **max_parallel** – the most runs at once.
- **options** – the executor’s options.

#### `property names: list[str]`

The analysed parameters, in the space’s order.

#### `rng(stream: Stream, key: int) → Generator`

The generator of one stream of this study’s seed.

#### `evaluate(units: ndarray, key: int) → ndarray`

One output value per row of `units`; `key` names the batch of runs.

Results of a sensitivity analysis: a table per parameter, a ranking and a plot.

Every method returns a [`SensitivityResult`](https://remipelloux.github.io/Modelly/apis/sensitivity.html#modelly.sensitivity.results.SensitivityResult) (or a subclass) whose `table` has one row per parameter. `ranking()` sorts it by the method’s main measure, most influential first; `to_dataframe()` returns a copy; `plot()` draws a Matplotlib figure (`figure.savefig(path)` writes it).

#### `class SensitivityResult(method: str, table: DataFrame, measure: str, info: dict[str, ~typing.Any]=<factory>)`

One analysis: `table` (index: parameter) and the measure ranking uses.

**Variables:**

- **method** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the method’s name.
- **table** (*pandas.DataFrame*) – one row per parameter.
- **measure** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the column `ranking` sorts by.
- **info** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **Any**]*) – how the analysis ran (samples, model runs, seed…).

#### `ranking() → DataFrame`

The table sorted by the main measure, most influential first.

#### `to_dataframe() → DataFrame`

A copy of the table, the parameter as a column.

#### `plot() → Any`

A bar chart of the main measure, parameters in ranking order.

#### `class MorrisResult(method: str, table: DataFrame, measure: str, info: dict[str, ~typing.Any]=<factory>)`

Morris screening: `mu`, `mu_star` and `sigma` of the elementary effects.

#### `plot() → Any`

`sigma` against `mu_star`: far right is influential, high is non-linear.

#### `class SobolResult(method: str, table: DataFrame, measure: str, info: dict[str, ~typing.Any]=<factory>)`

Sobol indices `S1` and `ST` with bootstrap intervals.

#### `plot() → Any`

First-order and total indices side by side, with their intervals.

#### `class OATResult(method: str, table: DataFrame, measure: str, info: dict[str, ~typing.Any]=<factory>, sweeps: DataFrame = <factory>)`

One-at-a-time sweeps: `sweeps` holds every evaluated value.

#### `plot() → Any`

The output along each parameter’s sweep, the others at their midpoint.

## Analysis files

Read a sensitivity analysis from a TOML file (what `modelly sensitivity spec.toml` runs).

The file reuses the experiment format; `[sensitivity]` picks the method:

```default
[experiment]
model = "model.py:SIR"          # a Model class, or module:function of the parameters
steps = 60
replicates = 2
seed = 1
outputs = ["infected"]          # the first output is analysed
store = "runs/sensitivity"      # optional

[space]
beta = { min = 0.1, max = 0.8 }
gamma = { min = 0.05, max = 0.3 }
population = 1000

[sensitivity]
method = "morris"               # oat, morris, sobol, pawn
statistic = "max"               # last, max, min, mean, sum
trajectories = 20               # the method's settings

[run]
executor = "processes"
```

#### `load_sensitivity(path: str | Path, method: str | None = None) → tuple[Callable[[...], Any], dict[str, Any]]`

The method a TOML file (or `method`) names and every keyword argument for it.
