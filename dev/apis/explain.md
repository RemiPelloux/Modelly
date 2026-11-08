# Causes and explanations

`modelly.explain` estimates effects, attributes outcomes, replays counterfactuals and computes Shapley values. How to use it is in [Causes and explanations](https://remipelloux.github.io/Modelly/dev/explain.html).

Average treatment effects, with the variance reduction of common random numbers measured.

`treatment_effect(run, control, treated, output)` estimates how much `treated` changes `output` against `control`, over `replicates` pairs of runs. With common random numbers replicate `r` of both arms gets the same seed, so each pair differs only by the treatment; the estimate is also computed with independent seeds, on separate runs, and the ratio of the two variances is reported: how many times fewer runs common random numbers need for the same precision.

`counterfactual(recorder, step, change, until, output)` asks the same question of one run that has already happened: from the recorded state at `step` (`modelly.timetravel`), the run is continued twice, once as it was and once with `change` applied, on the same random streams, or on `branches` reseeded pairs.

#### `class Effect(mean: float, low: float, high: float, paired_variance: float, independent_variance: float = nan, replicates: int = 0)`

An average effect and its interval.

**Variables:**

- **high** (*mean**, **low**,*) – the mean difference (treated minus control) and its interval.
- **paired_variance** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the variance of the per-replicate differences (common numbers).
- **independent_variance** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the variance of the difference with independent seeds, or NaN when it was not measured.
- **replicates** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the number of pairs.

#### `property variance_reduction: float`

How many times smaller the variance is with common random numbers.

#### `treatment_effect(run: Run, control: Mapping[str, Any], treated: Mapping[str, Any], output: str, *, replicates: int = 30, seed: int = 0, confidence: float = 0.95, measure_independent: bool = True, workers: int | None = 1) → Effect`

`treated` minus `control` on `output`, paired on common random numbers.

With `measure_independent` the control runs are compared with treated runs on other seeds too, which doubles the cost and gives `variance_reduction`. `workers` runs them over that many processes (`modelly.batch.run_batch`): the same results in the same order; 1, the default, runs them here one after another.

#### `counterfactual(recorder: Any, step: float, change: Callable[[Any], None], until: float, output: Callable[[Any], float], *, branches: int = 1, confidence: float = 0.95) → Effect`

The effect of `change` applied at `step` of a recorded run, read at `until`.

With one branch both continuations draw the same numbers as the recorded run; with several, pair `i` is reseeded from the run’s seed (`Recorder.branch`), the same seeds for the changed and the unchanged continuation.

Attribution: which agents, taken out of a run, change its outcome the most.

`attribute(build, candidates, output, steps=...)` reruns the model once per candidate agent with an intervention on that agent at the start (by default it is removed), on the same seed as the baseline, and measures how far the outcome moves. Over several seeds the effects are averaged per candidate, keyed by the agents’ unique ids, so a candidate is the same agent in every rerun of a seed. The agents whose removal moves the outcome most are the ones it depends on: in an outbreak, the index case; in a market, the trader the crash started from.

Removing an agent can shift the random draws that follow it, so the rerun is paired with the baseline but not identical to it apart from the agent; averaging over seeds smooths that out, and an intervention that keeps the agent (`intervene` setting its state) changes the draws less.

#### `remove(model: Any, agent: Any) → None`

The default intervention: the agent leaves the model.

#### `class Attribution(table: DataFrame, baseline: tuple[float, ...])`

The effect of intervening on each candidate, largest first.

**Variables:**

- **table** (*pandas.DataFrame*) – per candidate (its unique id): the mean change of the outcome (baseline minus intervened) and its interval over the seeds.
- **baseline** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*float*](https://docs.python.org/3/builtins/functions.html#float)*, **...**]*) – the outcome of each seed’s unchanged run.

#### `top(n: int = 5) → list[int]`

The unique ids of the `n` candidates with the largest effect.

#### `attribute(build: ~modelly.explain.attribution.Build, candidates: ~collections.abc.Callable[[~typing.Any], ~collections.abc.Sequence[~typing.Any]], output: ~collections.abc.Callable[[~typing.Any], float], *, steps: int, seeds: ~collections.abc.Sequence[int] = (0,), intervene: ~collections.abc.Callable[[~typing.Any, ~typing.Any], None] = <function remove>, confidence: float = 0.95, workers: int | None = 1) → Attribution`

Intervene on each candidate agent in turn; the outcome’s change, per candidate.

`build(seed)` makes a fresh model, `candidates(model)` lists the agents to try (in the freshly built model), `output(model)` reads the outcome after `steps` steps. `workers` reruns a seed’s candidates over that many processes (`modelly.batch.run_batch`), with the same results; 1, the default, reruns them here.

Shapley values of an emulator’s prediction: how much each parameter moved it.

`shapley(predict, point, background)` splits `predict(point) - mean(predict(background))` between the parameters exactly: the Shapley value of parameter `j` averages, over every subset `S` of the other parameters, how much setting `j` to its value in `point` changes the prediction when `S` is set too and the rest take their values from the background sample (the *interventional* value function). The values add up to the difference, as Shapley values must. Exact enumeration costs `2**d` background predictions for `d` parameters, fine for the ten or so parameters an emulator usually has; an emulator makes each one cheap.

`predict` is any function of unit-cube points `[point, dimension]` returning one value per point, such as `Emulator.select(name).predict_unit` of `modelly.emulate`.

**Reference:**

Lundberg, S. M. and Lee, S.-I. (2017). A unified approach to interpreting model predictions. Advances in Neural Information Processing Systems 30, 4765-4774.

#### `shapley(predict: Callable[[ndarray], ndarray], point: Sequence[float], background: ndarray, names: Sequence[str] | None = None) → dict[str, float]`

Each parameter’s Shapley value at `point` against `background`, exactly.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – for more than `MAX_DIMENSIONS` parameters, or shapes that disagree.
