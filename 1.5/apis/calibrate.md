# Calibration

`modelly.calibrate` fits parameters to observed data. How to use it is in [Calibration](https://remipelloux.github.io/Modelly/calibration.html).

## Methods

What every calibration method shares: model, priors, targets, seeds, runs, checkpoints.

A method subclasses [`Calibration`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.base.Calibration) and implements `run`. The base class turns parameter samples into batches of runs on the experiment executors, measures each point’s distance to the targets, and saves the whole calibration, state included, to a checkpoint that [`Calibration.load()`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.base.Calibration.load) resumes.

#### `exception CalibrationError`

A calibration cannot go on (no particle accepted, a checkpoint is unusable…).

#### `class Calibration(model: type | str, priors: Mapping[str, Prior], targets: Sequence[Target], steps: int = 100, replicates: int = 1, seed: int = 0, store: str | Path | None = None, fixed: Mapping[str, Any] | None = None)`

Base class: fit the priors’ parameters of `model` to `targets`.

**Parameters:**

- **model** – the Model class, or `"package.module:Class"` / `"path/model.py:Class"`.
- **priors** – `{parameter: Prior}` for every parameter to fit.
- **targets** – the observed quantities ([`Target`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.targets.Target)).
- **steps** – steps per run.
- **replicates** – runs per parameter point, averaged before the distance.
- **seed** – the root of every random stream: same seed, same result.
- **store** – the folder the runs are written to (a temporary one by default); a calibration rerun into the same folder reads the runs already there.
- **fixed** – parameters every run takes, not fitted.

Check the definition; nothing runs before `run`.

#### `property names: list[str]`

The fitted parameters, in the priors’ order.

#### `property simulator: Simulator`

The runs’ simulator, writing to the store (or a temporary folder).

#### `points(samples: Mapping[str, Sequence[Any]]) → list[dict[str, Any]]`

One parameter dict per sample, the fixed parameters included.

#### `evaluate(batch: Batch, execution: Execution) → tuple[ndarray, dict[str, ndarray]]`

Run `batch`; the total distance and every target’s summary, per point.

#### `measure(results: Sequence[Mapping[str, ndarray]]) → tuple[ndarray, dict[str, ndarray]]`

The total distance and every target’s summary of simulated `results`.

#### `posterior(samples: Mapping[str, Sequence[Any]], weights: ndarray, distances: ndarray, summaries: Mapping[str, ndarray]) → Posterior`

The Posterior of weighted samples, with what it needs to predict and plot.

#### `save(path: str | Path) → None`

Write the calibration and its progress to `path` (a pickle; trusted files only).

Every model, distance and summary function must be importable (no lambdas).

#### `classmethod load(path: str | Path) → Calibration`

The calibration [`save()`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.base.Calibration.save) wrote; `run` it again to go on where it stopped.

ABC-SMC: approximate Bayesian computation by sequential Monte Carlo.

Generation 0 samples the priors. Each later generation sets its tolerance to a quantile of the previous generation’s distances, proposes particles by drawing an ancestor by weight and moving it with the perturbation kernel ([`modelly.calibrate.kernels`](https://remipelloux.github.io/Modelly/apis/calibrate.html#module-modelly.calibrate.kernels)), keeps those whose distance is within the tolerance, and weights them by prior over proposal density (Toni et al., 2009; Beaumont et al., 2009).

Proposals are made in batches of `particles`; a generation keeps the first `particles` accepted in proposal order. Batch `b` of generation `g` draws from the stream `(PROPOSAL, g, b)` and runs with the seeds of `(g, b)`, so the posterior is the same on every executor and after a resume.

Example

```default
>>> calibration = ABCSMC(
...     model=Epidemic,
...     priors={"beta": Prior.uniform(0.05, 0.5), "gamma": Prior.log_normal(-2, 0.5)},
...     targets=[Target("infected", observed=cases)],
...     steps=60,
...     seed=2027,
... )
>>> posterior = calibration.run(budget=5000, executor="processes")
```

#### `class Accepted(samples: dict[str, list[Any]], distances: ndarray, summaries: dict[str, ndarray])`

The particles of one proposal batch that met the tolerance.

#### `class Generation(samples: dict[str, list[Any]], weights: ndarray, distances: ndarray, summaries: dict[str, ndarray], tolerance: float, runs: int, acceptance: float)`

One accepted population: samples, weights, distances, summaries and costs.

#### `property effective_sample_size: float`

Kish’s effective sample size of the normalised weights.

#### `class ABCSMC(*args: Any, particles: int = 100, quantile: float = 0.5, min_tolerance: float = 0.0, min_acceptance: float = 0.01, **kwargs: Any)`

ABC-SMC with an adaptive tolerance schedule.

Takes the [`Calibration`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.base.Calibration) arguments and:

**Parameters:**

- **particles** – the population size (and the size of a proposal batch).
- **quantile** – the next tolerance is this quantile of the last distances.
- **min_tolerance** – stop once the tolerance reaches this value.
- **min_acceptance** – stop when a generation accepts a smaller share of its proposals; also bounds the cost of one generation.

Check the settings; nothing runs before `run`.

#### `property runs: int`

Model runs made by the accepted generations.

#### `run(budget: int | None = None, generations: int = 5, executor: Any = 'serial', max_parallel: int | None = None, **options: Any) → Posterior`

Add generations until one of the stopping rules holds; the last posterior.

Stops after `generations` generations in all, before a generation that would take the model runs past `budget`, when the tolerance reaches `min_tolerance` or the acceptance rate falls below `min_acceptance`. `checkpoint=path` (in `options`) saves after every generation. Calling `run` again, after `load` or with a larger `generations`, goes on from the last generation.

#### `posterior_of(generation: Generation) → Posterior`

The Posterior of `generation`, with the run’s diagnostics in `info`.

#### `trace() → DataFrame`

One row per generation: tolerance, acceptance rate, effective sample size, runs.

ABC rejection: sample the priors, run every sample, keep the closest.

The simplest approximate Bayesian computation: `budget` parameter points are drawn from the priors (stream `(PROPOSAL, REJECTION_KEY)` of the seed), run as one batch on the chosen executor, and kept when their distance is within `tolerance`, or, without a tolerance, when they are among the `quantile` closest. The accepted samples have equal weights.

Example

```default
>>> calibration = ABCRejection(Epidemic, priors, targets, steps=60, seed=1)
>>> posterior = calibration.run(budget=2000, quantile=0.05)
```

#### `class ABCRejection(model: type | str, priors: Mapping[str, Prior], targets: Sequence[Target], steps: int = 100, replicates: int = 1, seed: int = 0, store: str | Path | None = None, fixed: Mapping[str, Any] | None = None)`

ABC rejection sampling over the priors (see the module docstring).

Check the definition; nothing runs before `run`.

#### `run(budget: int = 1000, quantile: float | None = 0.1, tolerance: float | None = None, executor: Any = 'serial', **options: Any) → Posterior`

Run `budget` prior samples and keep the closest (`max_parallel` in options).

`tolerance` keeps every sample within it; otherwise `quantile` keeps that share of the samples, the closest first.

The method of simulated moments: match simulated statistics to observed ones.

Each target contributes its observed moments (a series, or the statistics its `summary` returns). At a parameter point the replicate mean of the simulated moments gives the gap `g = m(theta) - m_observed` (scaled by the square root of each target’s weight), and the objective is `g' W g`. `W` is the weighting matrix: the identity, the inverse of the moments’ variances (`"diagonal"`) or of their covariance (`"optimal"`), both estimated from the replicates at the starting point, or a matrix you give.

The objective is minimised in the priors’ unit box with `scipy.optimize` (Nelder-Mead or Powell); every evaluation uses the same replicate seeds, so the search sees a deterministic function.

Example

```default
>>> fit = SimulatedMoments(Market, priors, targets, steps=200, replicates=8)
>>> fit.run(evaluations=150).best
```

#### `class SimulatedMoments(*args: Any, weighting: str | ndarray = 'identity', optimizer: str = 'Nelder-Mead', start: dict[str, float] | None = None, **kwargs: Any)`

Simulated method of moments (see the module docstring).

Takes the [`Calibration`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.base.Calibration) arguments and:

**Parameters:**

- **weighting** – `"identity"`, `"diagonal"`, `"optimal"` or a square matrix.
- **optimizer** – `"Nelder-Mead"` or `"Powell"`.
- **start** – the starting parameters (default: the prior medians).

Check the settings; nothing runs before `run`.

#### `moments(result: dict[str, ndarray]) → ndarray`

The scaled gaps of every replicate: `array[replicate, moment]`.

#### `objective(unit: ndarray, execution: Execution) → float`

`g' W g` at the unit-cube point `unit` (the evaluation is recorded).

#### `run(evaluations: int = 200, executor: Any = 'serial', max_parallel: int | None = None, **options: Any) → Posterior`

Minimise the objective with at most `evaluations` evaluations; the best point.

Bayesian optimisation of the targets’ distance: a basic Gaussian-process search.

A built-in, deliberately small optimiser for models too expensive for ABC: `initial` points of a Latin hypercube over the priors’ unit box, then, one point at a time, the candidate with the largest expected improvement under a Gaussian process ([`modelly.calibrate.gp`](https://remipelloux.github.io/Modelly/apis/calibrate.html#module-modelly.calibrate.gp)) fitted to every evaluation so far. Candidates are random points of the box from a seeded stream, so a run is reproducible. It returns the best point found, not a posterior distribution, and suits a handful of parameters and up to a few hundred evaluations; no external optimisation library is needed.

Example

```default
>>> search = BayesOpt(Epidemic, priors, targets, steps=60, replicates=4, seed=3)
>>> search.run(evaluations=40).best
```

#### `class BayesOpt(*args: Any, **kwargs: Any)`

Gaussian-process Bayesian optimisation of the total distance (see the module docstring).

Check the priors are continuous; nothing runs before `run`.

#### `run(evaluations: int = 30, initial: int = 10, executor: Any = 'serial', **options: Any) → Posterior`

`initial` design points (run together), then the rest one by one; the best point.

`max_parallel` and executor options go in `options`.

Bayesian optimisation by an outside library, behind a two-call adapter.

[`ExternalBayesOpt`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.external.ExternalBayesOpt) searches the same unit box over the priors as [`BayesOpt`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.bayesopt.BayesOpt), with the same common random numbers, but asks an outside optimiser where to run next. An optimiser is any object with `ask() -> unit point` and `tell(unit, value)`; `backend` names a built-in adapter or is a factory `(dimensions, seed) -> optimiser`.

The built-in adapter is `"optuna"`: an optuna study in memory, minimising the total distance, with optuna’s TPE sampler (a sequential model-based optimiser) seeded from the calibration’s seed, or any optuna sampler given as `sampler=`. optuna is imported only when the search starts: `pip install "modelly-abm[calibrate]"`. Like `BayesOpt`, it returns the best point found, not a posterior.

Example

```default
>>> search = ExternalBayesOpt(Epidemic, priors, targets, steps=60, seed=3)
>>> search.run(evaluations=40).best
```

#### `class Optimiser(*args, **kwargs)`

What an outside optimiser provides: a point to run, then its value.

#### `ask() → Sequence[float]`

The next point to evaluate, in the unit cube.

#### `tell(unit: Sequence[float], value: float) → None`

The objective at the point `ask` returned last (lower is better).

#### `class OptunaBackend(dimensions: int, seed: int, sampler: Any = None)`

optuna’s ask-and-tell interface over the unit cube, minimising.

**Parameters:**

- **dimensions** – the number of fitted parameters.
- **seed** – the seed of the default TPE sampler.
- **sampler** – an optuna sampler to use instead.

Create the in-memory study.

#### `ask() → list[float]`

The study’s next trial, as a unit point.

#### `tell(unit: Sequence[float], value: float) → None`

Close the open trial with `value`.

#### `class ExternalBayesOpt(*args: Any, backend: str | Callable[[...], Optimiser] = 'optuna', backend_options: dict[str, Any] | None = None, **kwargs: Any)`

Bayesian optimisation of the total distance by an outside optimiser.

**Parameters:**

- ***args** – as for [`Calibration`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.base.Calibration).
- **backend** – `"optuna"`, or a factory `(dimensions, seed, **options) -> Optimiser`.
- **backend_options** – keyword arguments of the backend (`sampler=` for optuna).
- ****kwargs** – as for [`Calibration`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.base.Calibration).

Check the priors and the backend; nothing runs before `run`.

#### `optimiser() → Optimiser`

A fresh optimiser over the box, seeded with the calibration’s seed.

#### `run(evaluations: int = 30, executor: Any = 'serial', **options: Any) → Posterior`

`evaluations` points, one at a time, where the optimiser asks; the best point.

`max_parallel` and executor options go in `options`. A rerun into the same store asks the same points (same seed) and reads their runs from the store.

What the optimising methods share: a unit box over the priors and common random numbers.

[`SimulatedMoments`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.moments.SimulatedMoments) and [`BayesOpt`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.bayesopt.BayesOpt) search the box spanned by the priors (their support, or the central 99.8 % of an unbounded one; log-scaled priors on a log scale). Every evaluation runs its point with the same replicate seeds (common random numbers), so the objective is a deterministic, smoother function of the parameters, and each evaluation is a batch of its own in the store.

#### `class UnitBox(priors: Mapping[str, Prior])`

The map between the unit cube and the priors’ search intervals.

One interval per prior; choices are refused.

#### `params(unit: Sequence[float] | ndarray) → dict[str, float]`

The parameters at `unit` (clipped to the cube).

#### `unit(params: Mapping[str, float]) → ndarray`

The position of `params` in the cube.

#### `class PointEstimate(*args: Any, **kwargs: Any)`

Base of the methods that return the best point found (a one-sample Posterior).

Check the priors are continuous; nothing runs before `run`.

#### `simulate(units: Sequence[Sequence[float] | ndarray] | ndarray, execution: Execution) → list[dict[str, ndarray]]`

Run each unit-cube point as its own batch, with common random numbers.

#### `record(unit: Sequence[float] | ndarray, value: float, summaries: Mapping[str, ndarray]) → float`

Keep one evaluation (parameters, objective, summaries); return `value`.

#### `trace() → DataFrame`

One row per evaluation: the parameters and the objective.

#### `estimate() → Posterior`

The best evaluation as a one-sample Posterior.

Perturbation kernels of ABC-SMC: move a particle, and the density of that move.

Continuous parameters move together under a multivariate normal whose covariance is twice the weighted covariance of the previous population (Beaumont et al., 2009). A choice keeps its value with probability `stay` and otherwise takes one of the other values, each equally likely.

#### `joint_logprior(priors: Mapping[str, Prior], samples: Mapping[str, Sequence[Any]]) → ndarray`

The log prior density of every sample (independent priors).

#### `class Kernel(priors: Mapping[str, Prior], population: Mapping[str, Sequence[Any]], weights: ndarray, covariance: ndarray, stay: float = 0.7)`

A perturbation kernel fitted to a weighted population of particles.

#### `property continuous: list[str]`

The names of the continuous parameters.

#### `property discrete: list[str]`

The names of the choice parameters.

#### `classmethod fit(priors: Mapping[str, Prior], samples: Mapping[str, Sequence[Any]], weights: ndarray) → Kernel`

The kernel for moving the weighted population `samples`.

#### `perturb(samples: Mapping[str, Sequence[Any]], rng: Generator) → dict[str, list[Any]]`

Each of `samples` moved once (they may leave the prior’s support).

#### `logpdf(new: Mapping[str, Sequence[Any]]) → ndarray`

`log K(new[i] | population[j])` as an array `[i, j]`.

#### `importance(new: Mapping[str, Sequence[Any]]) → ndarray`

Unnormalised log weights: prior over the population’s mixture density.

#### `propose(rng: Generator, count: int) → dict[str, list[Any]]`

`count` particles: ancestor drawn by weight and moved, both redrawn until inside.

Redrawing the ancestor too (Toni et al., 2009) makes the proposal the mixture truncated to the prior’s support, whose normalising constant is the same for every particle; re-moving the same ancestor would over-weight particles near a bound.

## Priors, targets and distances

Priors: what is believed about each parameter before the data are seen.

Example

```default
>>> import numpy as np
>>> prior = Prior.uniform(0.05, 0.5)
>>> values = prior.sample(np.random.default_rng(1), 3)
>>> bool(((values >= 0.05) & (values <= 0.5)).all())
True
>>> float(prior.logpdf(0.6))
-inf
```

Continuous priors sample and evaluate through `scipy.stats`; a choice draws one of its values. Every draw comes from the generator passed in, so the same seed gives the same samples.

#### `class Prior(kind: str, arguments: dict[str, ~typing.Any]=<factory>)`

A prior distribution over one parameter; build it with a class method.

**Variables:**

- **kind** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – one of `uniform`, `log_uniform`, `normal`, `log_normal`, `truncated_normal` and `choice`.
- **arguments** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **Any**]*) – the distribution’s parameters, by name.

#### `classmethod uniform(low: float, high: float) → Prior`

Every value in `[low, high]` equally likely.

#### `classmethod log_uniform(low: float, high: float) → Prior`

Uniform on a log scale over `[low, high]` (`low > 0`).

#### `classmethod normal(mean: float, sd: float) → Prior`

A normal distribution.

#### `classmethod log_normal(mu: float, sigma: float) → Prior`

A value whose logarithm is normal with mean `mu` and sd `sigma`.

#### `classmethod truncated_normal(mean: float, sd: float, low: float = -inf, high: float = inf) → Prior`

A normal distribution cut to `[low, high]`.

#### `classmethod choice(values: Sequence[Any], probabilities: Sequence[float] | None = None) → Prior`

One of `values`, equally likely unless `probabilities` are given.

#### `property discrete: bool`

Whether the prior is a choice among values.

#### `distribution() → Any`

The frozen `scipy.stats` distribution of a continuous prior (built once).

#### `sample(rng: Generator, size: int) → ndarray`

`size` independent draws from `rng`.

#### `logpdf(value: Any) → float | ndarray`

The log density (log probability for a choice); `-inf` off the support.

#### `bounds() → tuple[float, float]`

The support, or the central `1 - 2 * TAIL` interval of an unbounded prior.

#### `median() → Any`

The prior median (a choice: its most likely value).

Targets: what a calibration compares between the model and the data.

A [`Target`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.targets.Target) names an output the model records every step (an attribute, a method or a module-level function of the model, the same things an `Experiment` output or a `DataCollector` model reporter reads) and the observed values it should match:

```default
Target("infected", observed=cases)                         # the whole series
Target("infected", observed=[412.0], summary=peak)         # one statistic
Target("prey", observed=counts, distance=distance.mae, weight=0.5)
```

Without `summary` the observed series is matched to the end of the simulated one: `observed[-1]` against the value after the last step. With `summary`, `summary(series)` of every replicate is compared to `observed`. Replicates are averaged before the distance is taken.

#### `class Target(name: str, observed: ~typing.Any, distance: ~collections.abc.Callable[[~numpy.ndarray, ~numpy.ndarray], float] | str = <function rmse>, weight: float = 1.0, summary: ~collections.abc.Callable[[~numpy.ndarray], ~typing.Any] | None = None, output: str | ~collections.abc.Callable[[~typing.Any], ~typing.Any] | None = None)`

One observed quantity and how to measure the model’s distance to it.

**Parameters:**

- **name** – the column name; also the output read unless `output` is given.
- **observed** – the observed series, or the observed summary statistics.
- **distance** – a function `(simulated, observed) -> float` or the name of a built-in (`"rmse"`, `"mae"`, `"euclidean"`, `"wasserstein"`).
- **weight** – the factor of this target’s distance in the total.
- **summary** – a function of one simulated series (a 1-d array, step 0 first) returning the statistics compared to `observed`.
- **output** – what to record, when it is not `name`: an attribute path or a module-level function of the model.

#### `distance(observed: ndarray) → float`

Root mean squared error.

#### `property spec: str`

an attribute path or a reference.

**Type:**

The output as an experiment reads it

#### `check_length(steps: int) → None`

Refuse an observed series longer than a run (`steps + 1` values).

#### `replicate_values(series: ndarray) → ndarray`

What is compared, per replicate: `array[replicate, value]`.

#### `simulated(series: ndarray) → ndarray`

The replicate mean of what is compared, from `series[replicate, step]`.

#### `score(simulated: ndarray) → float`

This target’s weighted distance for one simulated summary.

#### `total_distance(targets: Sequence[Target], simulated: dict[str, ndarray]) → float`

The sum of the targets’ weighted distances.

Distances between a simulated summary and the observed one.

A distance is any function `distance(simulated, observed) -> float` of two arrays of the same shape; smaller is closer. Example:

```default
>>> import numpy as np
>>> rmse(np.array([1.0, 2.0]), np.array([1.0, 4.0]))
1.4142135623730951
>>> weighted([1.0, 0.0])(np.array([1.0, 2.0]), np.array([1.0, 4.0]))
0.0
```

Every built-in is a module-level function or a picklable object, so a calibration that uses them can be saved and resumed.

#### `rmse(simulated: ndarray, observed: ndarray) → float`

Root mean squared error.

#### `mae(simulated: ndarray, observed: ndarray) → float`

Mean absolute error.

#### `euclidean(simulated: ndarray, observed: ndarray) → float`

The Euclidean norm of the difference (for vectors of summary statistics).

#### `wasserstein(simulated: ndarray, observed: ndarray) → float`

The Wasserstein-1 distance between the two sets of values as distributions.

The values are compared as samples, whatever their order or count.

#### `class Weighted(weights: tuple[float, ...])`

Root of the weighted mean of squared errors; one weight per value.

#### `weighted(weights: Sequence[float]) → Weighted`

A weighted RMSE: `weights[i]` scales the squared error of value `i`.

## Posterior

The result of a calibration: weighted parameter samples and how well they fit.

Example

```default
>>> posterior = calibration.run(budget=2000)
>>> posterior.summary()  # mean, median, sd and HDI per parameter
>>> posterior.to_dataframe()  # one row per sample, with weight and distance
>>> posterior.predict(draws=20)  # posterior predictive runs
>>> posterior.plot()  # marginals, pairs, fit against the data
```

#### `weighted_quantile(values: ndarray, weights: ndarray, q: float) → float`

The `q` quantile of `values` under `weights` (the inverse of the weighted CDF).

#### `hdi(values: ndarray, weights: ndarray, probability: float) → tuple[float, float]`

The shortest interval holding `probability` of the weighted samples.

#### `class Posterior(samples: Mapping[str, list[Any]], weights: np.ndarray, distances: np.ndarray, summaries: Mapping[str, np.ndarray], calibration: Calibration)`

Weighted samples of the fitted parameters.

**Variables:**

- **samples** – `{parameter: values}`, one value per sample.
- **weights** – the normalised importance weights (all equal for rejection).
- **distances** – each sample’s total distance to the targets.
- **summaries** – `{target: array[sample, value]}`, what each sample simulated.
- **calibration** – the calibration that produced it (used by `predict`).

Keep the samples; the weights are normalised to sum to one.

#### `property effective_sample_size: float`

Kish’s effective sample size of the weights, `1 / sum(w**2)`.

#### `property best: dict[str, Any]`

The parameters of the sample closest to the data.

#### `to_dataframe() → DataFrame`

One row per sample: the parameters, `weight` and `distance`.

#### `numeric() → dict[str, ndarray]`

The parameters whose values are numbers, as float arrays.

#### `summary(probability: float = 0.95) → DataFrame`

Weighted mean, median, sd and highest-density interval per numeric parameter.

#### `resample(draws: int) → list[int]`

`draws` sample indices drawn with the weights, from the calibration’s seed.

#### `predict(draws: int = 20, executor: Any = 'serial', max_parallel: int | None = None, **options: Any) → DataFrame`

Run the model at `draws` posterior samples; one row per draw, replicate and step.

The samples are drawn with the weights from the calibration’s seed, and the runs go to `executor` (with `options`) like the calibration’s own.

#### `plot(probability: float = 0.95) → Any`

A Matplotlib figure: marginals and pairs of the parameters, fits against the data.

Matplotlib figures of a Posterior: marginals, pairs, and the fit to the data.

The figure is built with `matplotlib.figure.Figure` (no pyplot state), so it works the same in scripts, notebooks and without a display; save it with `figure.savefig(path)`.

#### `posterior_figure(posterior: Posterior, probability: float) → Any`

The figure of `Posterior.plot()`: pairs on the left, one fit per target on the right.

## Runs

Run batches of parameter points through the experiment executors and read them back.

Calibration and sensitivity analysis both ask the same question many times: “what does the model produce at these points?”. A [`Simulator`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.simulator.Simulator) answers it with the machinery of `modelly.experiments`: one [`RunTask`](https://remipelloux.github.io/Modelly/apis/experiments.html#modelly.experiments.tasks.RunTask) per (point, replicate), run on any executor, each writing its Parquet file to a store folder per batch.

Seeds follow the experiment discipline. A batch is named by a key of integers; its runs use `SeedSequence(entropy, spawn_key=(point, replicate))` with the entropy drawn from `SeedSequence(seed, spawn_key=(SIMULATION, *key))`, or the same entropy for every batch when the batch asks for common random numbers. The numbers therefore never depend on the executor, the worker count or the order of the runs, and a batch already in its folder is read, not rerun.

#### `class Stream(*values)`

The first spawn-key element of each independent random stream.

#### `exception SimulationError`

A run of a calibration or sensitivity batch raised.

#### `entropy(seed: int, *key: int) → int`

An integer drawn from `SeedSequence(seed, spawn_key=key)`.

#### `generator(seed: int, *key: int) → Generator`

The numpy Generator of the stream `key` of `seed`.

#### `class Execution(executor: Any = 'serial', max_parallel: int | None = None, options: Mapping[str, ~typing.Any]=<factory>)`

Where runs execute: an executor name (or instance), its parallelism and options.

Used as a context manager, `"processes"` keeps one pool of workers for every batch until the block ends (see [`modelly.calibrate.pool`](https://remipelloux.github.io/Modelly/apis/calibrate.html#module-modelly.calibrate.pool)).

#### `runner() → Executor`

The executor to submit a batch to.

#### `class Batch(key: tuple[int, ...], points: Sequence[Mapping[str, Any]], common: bool = False)`

Points to simulate under one key; `common` reuses the same seeds for every batch.

#### `class Simulator(model: str, outputs: dict[str, str], steps: int, replicates: int, seed: int, root: Path)`

A model, its outputs, steps and replicates, and the folder batches go to.

`run` returns, for every point, `{output: array[replicate, step]}` with `steps + 1` columns (a run that stopped early repeats its last value).

#### `tasks(batch: Batch) → list[RunTask]`

One task per (point, replicate) of `batch`.

#### `folder(batch: Batch) → Path`

The store folder of `batch`.

#### `run(batch: Batch, execution: Execution) → list[dict[str, ndarray]]`

Simulate every point of `batch` not yet in its folder; read them all.

#### `run_many(batches: Sequence[Batch], execution: Execution) → list[list[dict[str, ndarray]]]`

Run several batches in one submission to the executor; read each back.

A process executor that keeps its workers between batches.

ABC-SMC, simulated moments and Bayesian optimisation submit many small batches. The experiments’ `processes` executor starts a fresh pool for each `run` call (workers start with `forkserver` or `spawn` and import the model: about a second each time); this one starts it once and reuses it until `close`. Its outcomes are the same, task for task.

#### `class PooledProcessExecutor(**options: Any)`

`processes`, with one pool for every `run` call until `close`.

No pool until the first batch.

#### `run(tasks: Sequence[RunTask], max_parallel: int | None = None) → Iterator[RunOutcome]`

Run the tasks on the shared pool (sized by the first call’s `max_parallel`).

#### `close() → None`

Stop the workers.

A small Gaussian-process regressor on numpy and scipy (basic, by design).

Used by [`BayesOpt`](https://remipelloux.github.io/Modelly/apis/calibrate.html#modelly.calibrate.bayesopt.BayesOpt), the sensitivity emulator and `modelly.emulate`. Inputs are points of the unit cube; the kernel is a squared exponential with one length scale per input plus a noise term, fitted by maximising the log marginal likelihood with L-BFGS-B from a fixed start (`restarts=True` adds a few more starts and keeps the best). It is meant for a few hundred points in a handful of dimensions; for more, use a dedicated library.

Example

```default
>>> import numpy as np
>>> x = np.linspace(0, 1, 8)[:, None]
>>> gp = GaussianProcess.fit(x, np.sin(6 * x[:, 0]))
>>> mean, sd = gp.predict(np.array([[0.5]]))
>>> bool(abs(mean[0] - np.sin(3.0)) < 0.05)
True
```

#### `class GaussianProcess(x: ndarray, lengths: ndarray, noise: float, alpha: ndarray, factor: ndarray, mean: float, scale: float)`

A fitted Gaussian process: training data, hyperparameters, and the solved system.

#### `classmethod fit(x: ndarray, y: ndarray, *, restarts: bool = False) → GaussianProcess`

Fit to inputs `x[point, dimension]` in the unit cube and outputs `y[point]`.

`restarts` also starts the likelihood search from `RESTARTS` and keeps the most likely fit: slower, and much less often stuck at a fit that calls everything noise.

#### `classmethod solve(x: ndarray, standard: ndarray, hyperparameters: tuple[ndarray, float], standardisation: tuple[float, float]) → GaussianProcess`

The process with given `(lengths, noise)` through standardised outputs `standard`.

#### `predict(x: ndarray) → tuple[ndarray, ndarray]`

The predictive mean and standard deviation at the rows of `x`.

#### `covariance(a: ndarray, b: ndarray) → ndarray`

The predictive covariance `[row of a, row of b]` of the fitted function.

#### `property noise_variance: float`

The fitted noise (nugget) variance, in the output’s units.

#### `condition(x: ndarray, y: ndarray | None = None) → GaussianProcess`

The process with the points `x` (outputs `y`) added, hyperparameters kept.

Without `y` the new points take the predicted mean (the “kriging believer”): the mean is unchanged and the variance is what it would be after running them, which is how a batch of runs is chosen.

#### `expected_improvement(mean: ndarray, sd: ndarray, best: float) → ndarray`

Expected improvement below `best` (minimisation) of normal predictions.

## Calibration files

Read a calibration from a TOML file (what `modelly calibrate spec.toml` runs).

The file reuses the experiment format (`[experiment]`, `[space]`, `[run]`) and adds the priors, the targets and the method:

```default
[experiment]
model = "model.py:SIR"          # relative to this file, or package.module:Class
steps = 40
replicates = 1
seed = 7
store = "runs/calibration"      # optional; a temporary folder otherwise

[space]                         # a range is a uniform prior (log = true: log-uniform),
beta = { min = 0.05, max = 1.0 }  # an integer range or a list a choice,
population = 1000               # anything else a fixed parameter

[priors]                        # optional: other priors, by kind
gamma = { kind = "log_normal", mu = -2.3, sigma = 0.5 }

[[targets]]
name = "infected"
file = "cases.csv"              # or observed = [..]; column defaults to name
column = "cases"
distance = "rmse"               # or mae, euclidean, wasserstein, module:function
weight = 1.0

[calibration]
method = "abc_smc"              # abc_rejection, simulated_moments, bayes_opt, external_bayes_opt
particles = 100                 # the method's settings
budget = 3000                   # and its run() arguments

[run]
executor = "processes"
max_parallel = 4
```

#### `priors_and_fixed(document: Mapping[str, Any]) → tuple[dict[str, Prior], dict[str, Any]]`

The priors (from `[space]` and `[priors]`) and the fixed parameters.

#### `load_calibration(path: str | Path) → tuple[Calibration, dict[str, Any], RunSettings]`

The calibration a TOML file describes, its `run()` arguments and `[run]` settings.
