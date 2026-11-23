# Decisions

`modelly.decide` compares, costs and stress-tests strategies. How to use it is in [Decisions](https://remipelloux.github.io/Modelly/dev/decide.html).

Comparing strategies: paired replicates, intervals, rankings.

A *strategy* is a named set of parameters (an intervention, a policy) and its cost. `compare(run, strategies, replicates=..., seed=...)` runs every strategy `replicates` times; replicate `r` of every strategy gets the same seed (common random numbers), so the strategies face the same chance events and their differences are paired: the interval of a difference is the interval of the per-replicate differences, much narrower than two independent intervals would give. `run(params, seed)` builds and runs the model and returns its outputs as a mapping of numbers; `model_runner` makes one from a model class.

#### `class Strategy(name: str, params: ~collections.abc.Mapping[str, ~typing.Any] = <factory>, cost: float | ~collections.abc.Callable[[~modelly.decide.compare.Outputs], float] = 0.0)`

A named intervention: the parameters it sets and what it costs.

**Variables:**

- **name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – how tables and rankings call it.
- **params** ([*collections.abc.Mapping*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **Any**]*) – the model parameters it sets.
- **cost** ([*float*](https://docs.python.org/3/builtins/functions.html#float)* | *[*collections.abc.Callable*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)*[**[**modelly.decide.compare.Outputs**]**, *[*float*](https://docs.python.org/3/builtins/functions.html#float)*]*) – a fixed cost, or `cost(outputs)` computed from one run’s outputs.

#### `cost_of(outputs: Outputs) → float`

The cost of one run.

#### `replicate_seeds(seed: int, replicates: int) → list[int]`

One seed per replicate, the same for every strategy (common random numbers).

#### `model_runner(model_class: type, outputs: Mapping[str, Callable[[Any], float]], steps: int | None = None, base: Mapping[str, Any] | None = None, scenario: type | None = None) → Run`

A `run(params, seed)` that builds `model_class` and reads `outputs` after it runs.

With `scenario`, the parameters (`base` updated by the strategy’s) and the seed go to it; otherwise to the model’s constructor as keywords and `rng`. The model runs `steps` steps, or its own `run()` when `steps` is None.

#### `interval(values: ndarray, confidence: float = 0.95) → tuple[float, float, float]`

Mean and Student-t interval of the mean of `values`.

#### `class Comparison(runs: DataFrame, strategies: tuple[Strategy, ...], confidence: float = 0.95)`

Every run of every strategy, and summaries of them.

**Variables:**

- **runs** (*pandas.DataFrame*) – one row per (strategy, replicate): its seed, outputs and cost.
- **strategies** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*modelly.decide.compare.Strategy*](https://remipelloux.github.io/Modelly/dev/apis/decide.html#modelly.decide.compare.Strategy)*, **...**]*) – the strategies, in the order given; the first is the baseline.
- **confidence** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the level of every interval.

#### `property names: list[str]`

The strategies’ names, baseline first.

#### `values(output: str, name: str) → ndarray`

`output` of strategy `name`, by replicate.

#### `summary(output: str) → DataFrame`

Mean and interval of `output` per strategy.

#### `difference(output: str, baseline: str | None = None) → DataFrame`

Each strategy minus `baseline` (the first by default), paired by replicate.

#### `rank(output: str, lower_is_better: bool = True) → DataFrame`

Strategies by mean `output`, best first, with how often each was best.

`best_share` is the share of replicates in which the strategy had the best value: with common random numbers each replicate is one shared set of chance events, so it estimates the probability that the strategy is the best choice.

#### `compare(run: Run, strategies: Sequence[Strategy], *, replicates: int = 20, seed: int = 0, confidence: float = 0.95, workers: int | None = 1) → Comparison`

Run every strategy `replicates` times with common random numbers.

`workers` runs them over that many processes (`modelly.batch.run_batch`): the same results in the same order; 1, the default, runs them here one after another.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – without strategies, with two of the same name, or with fewer than two replicates (no interval).

Cost-effectiveness: what each strategy costs for what it achieves, against the others.

`cost_effectiveness(comparison, effect)` places every strategy by its mean cost and mean effect (cases averted, years of life gained), removes the *dominated* ones (another costs no more and achieves at least as much) and the *extendedly dominated* ones (a mix of two others would do better), and gives the incremental cost-effectiveness ratio (ICER) of each remaining strategy over the previous one on that frontier: the price of one more unit of effect. `net_benefit` turns a willingness to pay per unit of effect into one number per strategy and replicate, `wtp * effect - cost`, ranked with paired intervals.

**Reference:**

Drummond, M. F., Sculpher, M. J., Claxton, K., Stoddart, G. L. and Torrance, G. W. (2015). Methods for the Economic Evaluation of Health Care Programmes, 4th ed., ch. 4. Oxford University Press.

#### `cost_effectiveness(comparison: Comparison, effect: str, cost: str = 'cost') → DataFrame`

Mean cost and effect, status and ICER of each strategy, cheapest first.

#### `net_benefit(comparison: Comparison, effect: str, wtp: float, cost: str = 'cost') → DataFrame`

`wtp * effect - cost` per strategy, with intervals and best shares, best first.

Robust decision making: strategies that do well across many possible futures.

When the parameters of the world are uncertain (how transmissible the next variant is, how many people comply), a strategy chosen for one best guess can fail badly elsewhere. `robust(run, strategies, futures, output)` runs every strategy in every future, with common random numbers within a future, and reports per strategy: the mean outcome over the futures, the worst one, the *regret* (how much worse than the best strategy of that future) at its largest and on average, and the share of futures in which it meets a `threshold`. Strategies are ranked by their largest regret (minimax regret), the usual criterion when the futures cannot be given probabilities. `sample_futures` draws futures from ranges by Latin hypercube sampling, from a seed.

**Reference:**

Lempert, R. J., Popper, S. W. and Bankes, S. C. (2003). Shaping the Next One Hundred Years: New Methods for Quantitative, Long-Term Policy Analysis. RAND, MR-1626.

#### `sample_futures(ranges: Mapping[str, tuple[float, float]], n: int, seed: int = 0) → list[dict[str, float]]`

`n` futures, a Latin hypercube over `ranges` (`{name: (low, high)}`).

#### `class Robustness(outcomes: DataFrame, futures: tuple[Mapping[str, Any], ...], lower_is_better: bool, threshold: float | None)`

The outcome of every strategy in every future, and the summary that ranks them.

**Variables:**

- **outcomes** (*pandas.DataFrame*) – mean `output` per (strategy, future), strategies as rows.
- **futures** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*collections.abc.Mapping*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **Any**]**, **...**]*) – the futures, in column order.
- **lower_is_better** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)) – the direction of `output`.
- **threshold** ([*float*](https://docs.python.org/3/builtins/functions.html#float)* | **None*) – the satisficing level, or None.

#### `regret() → DataFrame`

How much worse each strategy is than the best one of each future.

#### `summary() → DataFrame`

Mean, worst, largest and mean regret, satisficing share; minimax regret first.

#### `robust(run: Run, strategies: Sequence[Strategy], futures: Sequence[Mapping[str, Any]], output: str, *, lower_is_better: bool = True, replicates: int = 5, seed: int = 0, threshold: float | None = None, workers: int | None = 1) → Robustness`

Run every strategy in every future; the outcomes and their robustness summary.

A strategy’s parameters override the future’s where both set one. `workers` runs them over that many processes (`modelly.batch.run_batch`): the same results in the same order; 1, the default, runs them here one after another.

Intervention optimisation: search the parameters of a policy for the best outcome (Optuna).

`optimise(run, space, objective, trials=...)` lets Optuna’s TPE sampler propose policy parameters from `space` (`{name: (low, high)}`, or a list of choices), evaluates each proposal on the same replicate seeds (common random numbers, so two proposals differ only by the policy), and keeps the best. The sampler is seeded from `seed`, and trials run one after another, so the same call gives the same trials and the same answer. Optuna is an optional dependency: `pip install "modelly-abm[decide]"`.

**Reference:**

Akiba, T., Sano, S., Yanase, T., Ohta, T. and Koyama, M. (2019). Optuna: a next-generation hyperparameter optimization framework. KDD 2019, 2623-2631.

#### `class Optimum(params: dict[str, Any], value: float, trials: DataFrame)`

The best parameters found, their objective, and every trial.

**Variables:**

- **params** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **Any**]*) – the best proposal.
- **value** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – its objective, averaged over the replicates.
- **trials** (*pandas.DataFrame*) – one row per trial: its parameters and objective.

#### `optimise(run: Run, space: Space, objective: Callable[[Outputs], float], *, trials: int = 50, replicates: int = 5, seed: int = 0, minimise: bool = True, fixed: Mapping[str, Any] | None = None, workers: int | None = 1) → Optimum`

Search `space` for the parameters with the best mean `objective`.

Trials run one after another (the sampler learns from each); `workers` runs a trial’s replicates over that many processes, with the same results (1 runs them here).

The vaccination study of the decisions guide: which age group should get the doses?

The age-structured SEIR zoo model with 10,000 doses to give before an epidemic: to children, to adults, to seniors, or to nobody. Each strategy is run with common random numbers; the outputs are the infections and the deaths (an illustrative infection fatality ratio per age group), the cost is the doses plus the care of each infection. The numbers are illustrative, not a recommendation: see the age_seir model card.

#### `vaccination_study(replicates: int = 20, seed: int = 7) → Comparison`

Run the four strategies; `rank`, `difference` and the cost tables read it.
