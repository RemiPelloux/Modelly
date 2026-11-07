# Stream

Live observations for running models (provisional, new in 1.4): sources that hand out observations as they arrive, observation operators that read the same quantities from a model, ensembles of replicates advanced in lock step, and the filters that keep an ensemble close to the observations. The [data assimilation tutorial](https://remipelloux.github.io/Modelly/dev/assimilation.html) walks through all of them on a synthetic truth.

Module

Contents

modelly.stream.sources

Observation, ReplaySource, CSVSource, HTTPSource, due

modelly.stream.connectors

MQTTSource (extra mqtt), KafkaSource (extra kafka)

modelly.stream.operators

ObservationOperator

modelly.stream.ensemble

Ensemble, derived_seed, replicate_scenarios

modelly.stream.particle

ParticleFilter, FilterStep, systematic_resample, effective_sample_size

modelly.stream.kalman

EnsembleKalmanFilter, enkf_update

modelly.stream.bands

forecast_band, weighted_quantiles, quantile_column

Methods: the bootstrap particle filter of Gordon, Salmond & Smith (1993) with systematic resampling (Douc & Cappé 2005); the stochastic ensemble Kalman filter of Evensen (1994, 2003) with perturbed observations (Burgers, van Leeuwen & Evensen 1998). Full references are in the tutorial.

Bands (`Ensemble.band`, `Ensemble.forecast`, `ParticleFilter.band`, `ParticleFilter.forecast`) are long-format DataFrames with the columns `time`, `quantity`, `mean` and one `q<level>` per quantile (`q0.05`, `q0.5`, `q0.95` by default): plain data for plots and live views.

Where observations come from: a replayed table, a growing CSV file, an HTTP endpoint.

Every source has `poll(until=None)`: the observations it has not handed out yet, in time order, up to `until` when given (later ones wait for a later poll). A source never hands out an observation twice, so a loop that polls before each model step sees each data point exactly once. An observation that arrives after a later one was handed out is dropped: a run cannot go back to use it.

#### `class Observation(time: float, values: Mapping[str, float])`

Values observed at one time; `values` maps a quantity to a number.

#### `class ReplaySource(records: Any, *, time: str = 'time')`

Observations from memory: a list of records, or a pandas DataFrame.

Replay `records` (mappings with a `time` field, or a DataFrame).

#### `poll(until: float | None = None) → list[Observation]`

The observations not handed out yet, up to `until`.

#### `class CSVSource(path: str | Path, *, time: str = 'time')`

A CSV file that grows: each poll reads the rows appended since the last one.

Follow `path`; its first line is the header.

#### `poll(until: float | None = None) → list[Observation]`

Read complete new lines, then hand out what is due.

#### `class HTTPSource(url: str, *, time: str = 'time', fetch: ~collections.abc.Callable[[str], bytes] = <function _get>, parse: ~collections.abc.Callable[[bytes], ~collections.abc.Iterable[~collections.abc.Mapping[str, ~typing.Any]]] = <function loads>)`

An endpoint returning a JSON list of records; each poll fetches it again.

Poll `url`; `fetch` and `parse` replace the HTTP call and the JSON decoding.

#### `poll(until: float | None = None) → list[Observation]`

Fetch, keep records not seen before, then hand out what is due.

#### `due(source: Any | Iterable[Observation], until: float | None = None) → list[Observation]`

The observations of `source` up to `until`, in the order it gives them.

`source` is a stream source (anything with `poll(until)`) or an iterable of observations, such as a list.

Message-broker sources: MQTT topics and Kafka topics (optional extras).

Both behave like the other stream sources: `poll(until=None)` hands out the observations received since the last poll, in time order, each once. A message’s payload is a JSON record with a `time` field (or a list of them); `parse` replaces the decoding.

The client libraries are optional and imported only when a source builds its own client:

```default
pip install "modelly-abm[mqtt]"    # paho-mqtt
pip install "modelly-abm[kafka]"   # confluent-kafka
```

Pass `client=` (MQTT) or `consumer=` (Kafka) to use one you configured yourself, with authentication, TLS and so on, or a stand-in in tests.

#### `class MQTTSource(topic: str, *, host: str = 'localhost', port: int = 1883, client: ~typing.Any = None, time: str = 'time', parse: ~collections.abc.Callable[[bytes], ~typing.Any] = <function loads>)`

Observations published to an MQTT topic (paho-mqtt).

Subscribe to `topic` on the broker at `host:port`, or through `client`.

A `client` needs `subscribe(topic)` and an `on_message` attribute, as a paho `Client` has; it is used as given (connected, its loop running). Messages arrive on the client’s thread and wait in a queue for the next `poll`.

#### `poll(until: float | None = None) → list[Observation]`

Decode the messages received since the last poll, then hand out what is due.

#### `close() → None`

Stop and disconnect the client when this source created it.

#### `class KafkaSource(topic: str, *, config: ~collections.abc.Mapping[str, ~typing.Any] | None = None, consumer: ~typing.Any = None, time: str = 'time', parse: ~collections.abc.Callable[[bytes], ~typing.Any] = <function loads>, timeout: float = 1.0)`

Observations from a Kafka topic (confluent-kafka).

Consume `topic` with a consumer built from `config`, or with `consumer`.

`config` is the confluent-kafka configuration, for example `{"bootstrap.servers": "broker:9092", "group.id": "twin"}`. A `consumer` needs `subscribe([topic])`, `consume(num_messages, timeout)` and `close()`. Each poll waits at most `timeout` seconds.

#### `poll(until: float | None = None) → list[Observation]`

Read the messages waiting on the topic, then hand out what is due.

Messages that carry an error (such as the end of a partition) are kept in `errors` instead of being decoded.

#### `close() → None`

Leave the consumer group and close the consumer.

Observation operators: what a model would report if it were observed like the world.

An operator names each observed quantity and how to read it from a model:

```default
observe = ObservationOperator(
    cases=lambda m: m.new_cases,
    hospital=lambda m: m.count("hospitalised"),
)
observe(model)                      # {"cases": 41.0, "hospital": 7.0}
observe.residuals(model, obs)       # observed minus modelled, for the quantities obs has
```

`log_likelihood` scores a model against an observation under independent Gaussian errors; the particle filter weights replicates with it.

#### `class ObservationOperator(**quantities: Callable[[Any], float])`

Maps a model to the quantities an observation reports.

One callable per observed quantity, taking the model.

#### `property names: tuple[str, ...]`

The observed quantities, in declaration order.

#### `residuals(model: Any, observation: Observation) → dict[str, float]`

Observed minus modelled, for the quantities both the operator and `observation` have.

#### `log_likelihood(model: Any, observation: Observation, sd: float | Mapping[str, float]) → float`

Log density of `observation` given `model` under independent Gaussian errors.

`sd` is one standard deviation for every quantity, or one per quantity. Quantities the observation lacks do not count.

Ensembles: replicates of one scenario advanced in lock step.

An [`Ensemble`](https://remipelloux.github.io/Modelly/dev/apis/stream.html#modelly.stream.ensemble.Ensemble) builds `n` models from one scenario, each with a seed spawned from the scenario’s seed sequence, so replicate `i` gets the seed `Scenario.spawn_replications(n)[i]` gets on a fresh scenario:

```default
ensemble = Ensemble(Epidemic, EpidemicScenario(rng=7), 40)
ensemble.advance(10)                      # every replicate to time 10
ensemble.band(observe)                    # quantiles across replicates, a DataFrame
```

Replicates run one after the other in this process, in index order: the ensemble is deterministic for a seed. The assimilation filters ([`modelly.stream.particle`](https://remipelloux.github.io/Modelly/dev/apis/stream.html#module-modelly.stream.particle), [`modelly.stream.kalman`](https://remipelloux.github.io/Modelly/dev/apis/stream.html#module-modelly.stream.kalman)) work on an ensemble: they weight, duplicate and adjust its replicates between advances.

Every random draw the ensemble or a filter makes outside the models comes from a seed sequence derived from the scenario’s with a domain of its own (`derived_seed`), so no derived stream equals a replicate’s or an agent’s.

#### `derived_seed(root: SeedSequence, domain: int, *key: int) → SeedSequence`

The seed sequence of `key` in `domain`, below `root`.

`SeedSequence.spawn` hands out keys `(*root.spawn_key, i)`; these keys are one level deeper and start with `domain`, a number far above any replicate count, so they never collide with a spawned seed.

#### `replicate_scenarios(scenario: Scenario, n: int) → list[Scenario]`

`n` replicates of `scenario`, as `spawn_replications(n)` on a fresh one.

The scenario’s seed sequence is left as it was, so building a second ensemble from the same scenario gives the same replicates.

#### `class Ensemble(factory: Callable[..., Model], scenario: Scenario, n: int, *, prior: Prior | None = None)`

`n` replicates of a model, built from one scenario with spawned seeds.

Build `factory(scenario=replicate)` for each of `n` replicate scenarios.

A model class is a factory. `prior` maps a model attribute to a callable drawing its starting value from a numpy generator: each replicate gets its own draw, set after the model is built and before it runs, from a generator derived from the scenario’s seed.

#### `seed(domain: int, *key: int) → SeedSequence`

A seed sequence derived from the scenario’s (see `derived_seed`).

#### `property time: float`

The time every replicate has reached.

#### `advance(until: float) → None`

Run every replicate to time `until`, one after the other.

Nothing happens when the replicates are already at `until`.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – If `until` is before the current time.

#### `values(operator: ObservationOperator) → np.ndarray`

`operator` read from every replicate: one row per replicate, one column per quantity.

#### `resample(indices: Sequence[int], reseed: Callable[[int], SeedSequence]) → None`

Replace the replicates by `models[i] for i in indices`, copying duplicates.

The first slot that takes a replicate keeps the model itself; every other slot gets a checkpoint copy (`modelly.core.checkpoint.checkpoint_bytes()`) reseeded in place from `reseed(slot)`, so duplicates diverge from their next draw on. A copy is a full checkpoint, so it holds every agent, space, column and scheduled event of the original.

Note

Per-agent streams (`agent_streams = True`) are copied, not reseeded: only `model.random` and `model.rng` are.

#### `band(operator: ObservationOperator, quantiles: Sequence[float] = (0.05, 0.5, 0.95), weights: Sequence[float] | None = None) → pd.DataFrame`

Mean and quantiles of `operator` across replicates, at the current time.

One row per quantity, with columns `time`, `quantity`, `mean` and one `q<level>` per quantile (`q0.05`, `q0.5`, …): plain data for a plot or a live view. `weights` weight the replicates (equal by default).

#### `forecast(operator: ObservationOperator, until: float, *, every: float = 1.0, quantiles: Sequence[float] = (0.05, 0.5, 0.95), weights: Sequence[float] | None = None) → pd.DataFrame`

The band of `operator` from now to `until`, every `every` time units.

The forecast runs checkpoint copies of the replicates: the ensemble itself stays where it is. The frame has the columns of `band`, one row per time and quantity, the current time first.

Particle filter: keep an ensemble of runs close to the observations.

The bootstrap filter of Gordon, Salmond & Smith (1993), also called sequential importance resampling. Each replicate of an [`Ensemble`](https://remipelloux.github.io/Modelly/dev/apis/stream.html#modelly.stream.ensemble.Ensemble) is a particle. At each observation the replicates run to its time (the model itself is the proposal), each is weighted by [`ObservationOperator.log_likelihood`](https://remipelloux.github.io/Modelly/dev/apis/stream.html#modelly.stream.operators.ObservationOperator.log_likelihood), and when the effective sample size falls below `threshold * n` the ensemble is resampled with systematic resampling (Douc & Cappé 2005; Kitagawa 1996): a replicate drawn more than once is duplicated through a checkpoint and the duplicates are reseeded so they diverge:

```default
pf = ParticleFilter(ensemble, observe, sd=5.0)
pf.run(source)                       # assimilate every observation
pf.estimate()                        # weighted mean of each quantity now
pf.forecast(until=60)                # quantile bands ahead, a DataFrame
```

For a seed the filter is deterministic: the uniform of each systematic resampling comes from a generator derived from the scenario’s seed, and duplicate `slot` of resampling `g` is reseeded from the derived key `(RESAMPLE_DOMAIN, g, slot)`. Two runs give bit-identical weights and replicates, with the compiled core or the pure-Python one.

References

Gordon, N. J., Salmond, D. J. & Smith, A. F. M. (1993). Novel approach to nonlinear/non-Gaussian Bayesian state estimation. IEE Proceedings F, 140(2), 107-113. Douc, R. & Cappé, O. (2005). Comparison of resampling schemes for particle filtering. ISPA 2005, 64-69.

#### `effective_sample_size(weights: Sequence[float]) → float`

Kish’s effective sample size of `weights`: `1 / sum(w**2)` once they sum to one.

#### `systematic_resample(weights: Sequence[float], uniform: float) → ndarray`

The replicates systematic resampling keeps, one index per slot, in order.

Slot `k` takes the replicate whose cumulative weight first exceeds `(uniform + k) / n`; one uniform in `[0, 1)` decides every slot, which gives the lowest resampling variance of the usual schemes (Douc & Cappé 2005).

#### `class FilterStep(time: float, ess: float, resampled: bool, log_evidence: float)`

What one assimilated observation did to the ensemble.

`log_evidence` is the log of the observation’s likelihood averaged over the weighted replicates before it, an estimate of `log p(y_t | y_<t)`; the sum over steps estimates the log marginal likelihood of the data.

#### `class ParticleFilter(ensemble: Ensemble, operator: ObservationOperator, sd: float | Mapping[str, float], *, threshold: float = 0.5)`

Bootstrap particle filter over an ensemble (Gordon et al. 1993).

Weight `ensemble` against observations read through `operator`.

`sd` is the observation error, one standard deviation for every quantity or one per quantity. `threshold` is the fraction of the ensemble size under which the effective sample size triggers a resampling: `1.0` resamples at every observation.

#### `property weights: ndarray`

The normalised weight of each replicate.

#### `property ess: float`

The effective sample size of the current weights.

#### `property resamplings: int`

How many times the ensemble has been resampled.

#### `assimilate(observation: Observation) → FilterStep`

Run the ensemble to `observation`, weight it, resample when the ESS is low.

#### `run(source: object | Iterable[Observation], until: float | None = None) → list[FilterStep]`

Assimilate every observation `source` has, up to `until`.

`source` is a stream source (anything with `poll(until)`) or an iterable of observations in time order (see `sources.due`).

#### `estimate(operator: ObservationOperator | None = None) → dict[str, float]`

The weighted mean of each quantity of `operator` (the filter’s own by default).

#### `band(operator: ObservationOperator | None = None, quantiles: Sequence[float] = (0.05, 0.5, 0.95)) → pd.DataFrame`

The weighted band of `operator` now (see `Ensemble.band()`).

#### `forecast(until: float, operator: ObservationOperator | None = None, *, every: float = 1.0, quantiles: Sequence[float] = (0.05, 0.5, 0.95)) → pd.DataFrame`

The weighted band ahead to `until` (see `Ensemble.forecast()`).

#### `property history: DataFrame`

time, ESS, resampled, log evidence.

**Type:**

One row per assimilated observation

Ensemble Kalman filter for continuous parameters (state/parameter augmentation).

The stochastic ensemble Kalman filter of Evensen (1994, 2003) with perturbed observations (Burgers, van Leeuwen & Evensen 1998). The quantities it adjusts are named model attributes: parameters such as a contact rate, or any continuous state the model reads back. At each observation the replicates run to its time; with `X` the attributes (one row per replicate), `Y` what the operator reads from each and `R` the observation error variance:

```default
K   = cov(X, Y) (cov(Y, Y) + R)^-1
X_i = X_i + K (y + e_i - Y_i),      e_i ~ N(0, R)
```

Agent-level state is left alone: an agent-based model is rarely a vector the filter could shift, so the attributes are where it learns. Parameters can be kept in a range with `bounds`, clipping after each update:

```default
enkf = EnsembleKalmanFilter(ensemble, observe, sd=4.0, parameters=["beta"],
                            bounds={"beta": (0.0, 2.0)})
enkf.run(source)
enkf.estimate()                      # {"beta": 0.31}, the ensemble mean
```

The perturbations come from a generator derived from the scenario’s seed, so the filter is deterministic for a seed.

References

Evensen, G. (1994). Sequential data assimilation with a nonlinear quasi-geostrophic model using Monte Carlo methods to forecast error statistics. Journal of Geophysical Research, 99(C5), 10143-10162. Burgers, G., van Leeuwen, P. J. & Evensen, G. (1998). Analysis scheme in the ensemble Kalman filter. Monthly Weather Review, 126(6), 1719-1724. Evensen, G. (2003). The Ensemble Kalman Filter: theoretical formulation and practical implementation. Ocean Dynamics, 53(4), 343-367.

#### `enkf_update(states: ndarray, predicted: ndarray, observed: ndarray, variance: ndarray) → ndarray`

The EnKF analysis of `states` (replicates by attributes).

`predicted` holds what each replicate would observe (replicates by quantities), `observed` one perturbed observation per replicate (same shape) and `variance` the observation error variance of each quantity.

#### `class EnsembleKalmanFilter(ensemble: Ensemble, operator: ObservationOperator, sd: float | Mapping[str, float], parameters: Sequence[str], *, bounds: Mapping[str, tuple[float, float]] | None = None)`

Stochastic EnKF with perturbed observations (Evensen 1994, 2003).

Adjust the `parameters` attributes of `ensemble` to fit the observations.

`sd` is the observation error, one standard deviation for every quantity or one per quantity. `bounds` maps a parameter to the `(low, high)` range it is clipped to after each update.

#### `states() → ndarray`

The adjusted attributes: one row per replicate, one column per parameter.

#### `assimilate(observation: Observation) → dict[str, float]`

Run the ensemble to `observation` and update the parameters.

Returns the ensemble mean of each parameter after the update; an observation with none of the operator’s quantities changes nothing.

#### `run(source: object | Iterable[Observation], until: float | None = None) → list[dict[str, float]]`

Assimilate every observation `source` has, up to `until`.

`source` is a stream source (anything with `poll(until)`) or an iterable of observations in time order (see `sources.due`).

#### `estimate() → dict[str, float]`

The ensemble mean of each parameter.

#### `property history: DataFrame`

time, then each parameter’s mean and `<name>_sd`.

**Type:**

One row per observation

Quantile bands across an ensemble, as plain DataFrames.

A band is the spread of the observed quantities across replicates at a time: the (weighted) mean and a few quantiles. Rows are long-format, one per time and quantity, so a plot, a table or a live view (Studio) reads them without knowing anything about ensembles:

```default
time  quantity  mean   q0.05  q0.5   q0.95
12.0  cases     41.3   30.0   40.5   55.2
```

Weighted quantiles put each replicate’s weight at the midpoint of its step in the cumulative weights and interpolate linearly between them; with equal weights this is the Hazen definition (Hyndman & Fan 1996, definition 5).

#### `quantile_column(level: float) → str`

The column of quantile `level`: `q0.05`, `q0.5`, …

#### `weighted_quantiles(values: Sequence[float], weights: Sequence[float] | None, quantiles: Sequence[float]) → ndarray`

Quantiles of `values` weighted by `weights` (equal when `None`).

#### `forecast_band(models: Sequence[Model], operator: ObservationOperator, until: float, *, every: float = 1.0, quantiles: Sequence[float] = (0.05, 0.5, 0.95), weights: Sequence[float] | None = None) → pd.DataFrame`

Run checkpoint copies of `models` to `until`, a band at every forecast time.

The times are the models’ current time, then every `every` time units, ending exactly at `until`; `models` themselves do not move.
