# Scenarios

`modelly.scenarios` describes the parameters of a run as a typed `Scenario` (with its seed), runs many scenarios and keeps their results in a `Store`.

Module

Contents

modelly.scenarios.scenario

Scenario

modelly.scenarios.runner

run_scenarios, RunConfiguration

modelly.scenarios.sampling

rescale_samples

modelly.scenarios.store

Store, RunId, RunRecord and the in-memory store

modelly.scenarios.exceptions

the exceptions raised while running scenarios

## Scenario

Base Scenario class.

#### `class Scenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

A Scenario class for defining model parameters and experiments.

Supports both simple instantiation and type-hinted subclassing:

```default
# Simple usage
scenario = Scenario(rng=42, density=0.8, minority_pc=0.5)

# Type-hinted subclass (recommended for complex models)
class MyScenario(Scenario):
    citizen_density: float = 0.7
    cop_vision: int = 7
    movement: bool = True

scenario = MyScenario(rng=42, cop_vision=10)  # Override defaults
```

**Variables:**

- **scenario_id** – A unique identifier for this scenario, auto-generated starting from 0
- **experiment_id** – Identifies the design point (e.g., row in a QMC sample matrix)
- **replication_id** – Identifies the stochastic replication within a design point
- **rng** – Random number generator seed value

Notes

All parameters are accessible via attribute access (scenario.param). Class-level attributes in subclasses serve as default values. Scenario instances are frozen after initialisation; parameters cannot be modified. To create replications with derived seeds, use spawn_replications().

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `to_dict() → dict[str, Any]`

Return dict representation of the scenario.

Seed_sequence_entropy and seed_sequence_spawn_key together can be used to reconstruct the SeedSequence.

#### `spawn_replications(n: int) → list[Scenario]`

Spawn n replications of this scenario with deterministically derived seeds.

Each replication has identical user provided parameters but a unique random number generator and replication_id. The rng is spawned from the original rng of the base scenario instance. Indexing for replication_id starts from 0. This assumes that the instance on which this is called has replication_id == PARENT_REPLICATION_ID. If this assumption does not hold, a user warning is issued.

**Parameters:**

**n** – Number of replications to create.

**Returns:**

A list of n Scenario instances with replication_id 0..n-1.

#### `classmethod from_dataframe(experiments: DataFrame, *, rng: int | integer | Sequence[int] | SeedSequence | None = None, replications: int | None = None) → list[Scenario]`

Turn a dataframe into a list of scenarios.

**Parameters:**

- **experiments** – Dataframe containing the parameters for the scenarios.
- **rng** – the number of random seeds to use or a list of seeds.
- **replications** – the number of replications to create for each scenario

**Returns:**

a list of scenario instances

If rng is an integer, numpy will be used to generate that many seed values.

#### `classmethod from_ndarray(experiments: ndarray, parameter_names: list[str], *, rng: int | integer | Sequence[int] | SeedSequence | None = None, replications: int | None = None) → list[Scenario]`

Turn a numpy array into a list of scenarios.

**Parameters:**

- **experiments** – Dataframe containing the parameters for the scenarios.
- **parameter_names** – the names of the parameters
- **rng** – the number of random seeds to use or a list of seeds.
- **replications** – the number of replications to create for each scenario

**Returns:**

a list of scenario instances

If rng is an integer, numpy will be used to generate that many seed values.

## Running scenarios

Classes for running parameter sweeps over scenarios.

#### `class RunConfiguration(model_class: type[Model[Any, Any]], until: float | int, model_args: list[Any] | None = None, model_kwargs: dict[str, Any] | None = None, outcomes: str | list[str] | None = None, data_recorder_attr_name: str = 'data_recorder')`

Defines how a single Scenario is executed and what is extracted from it.

Can be used as is for simple use cases or subclassed by overriding one or more of the following methods

- `instantiate_model` — construct a Model from a Scenario (default: `model_class(*model_args, scenario=scenario, **model_kwargs)`).
- `run_model` — advance the model. Default delegates to `model.run_until` based on the `until` attribute. Override for alternative run control
- `extract_output` — return a dict with outcome names as key and dataframes as values

Stopping is the model’s responsibility. `RunConfiguration` only chooses which run primitive to call.

Initialize a RunConfiguration object.

**Parameters:**

- **model_class** – the model class to instantiate
- **until** – until which time to run the model
- **model_args** – any additional model arguments
- **model_kwargs** – any additional model keyword arguments
- **outcomes** – the outcomes to extract. If None, extract all outcomes.
- **data_recorder_attr_name** – the name of the data recorder attribute to use on the model

#### `instantiate_model(scenario: Scenario) → Model[Any, Any]`

Instantiate the model.

#### `run_model(model: Model[Any, Any]) → None`

Run the model.

#### `extract_output(model: Model[Any, Any]) → dict[str, pd.DataFrame]`

Extract output from model.

#### `run_scenarios(scenarios: Iterable[Scenario], config: RunConfiguration, *, executor: Executor | None = None, store: Store | None = None, progress: bool = True, workers: int | None = None) → Store`

Run the scenarios and return a Store object.

**Parameters:**

- **scenarios** – an iterable of scenarios to run Scenarios to execute. For replications, construct these via `MyScenario.from_dataframe(df, replications=n)` — replication is handled at scenario construction, not here.
- **config** – a RunConfiguration instance Per-scenario execution unit. Must be picklable when using a distributed executor (e.g., ProcessPoolExecutor).
- **executor** – an executor to run the scenarios Execution backend. If None, scenarios run sequentially in the calling thread (useful for debugging and small experiments). Otherwise, pass a user-constructed executor; its lifetime is the caller’s responsibility (use a `with` block).
- **store** – the Storage backend to use
- **progress** – whether to display the progress Display a progress bar via `tqdm` if installed.
- **workers** – run the scenarios in this many processes A shortcut for passing a `ProcessPoolExecutor`: the pool is created and closed here. Ignored when `executor` is given. The model class, the scenarios and the config must be importable (picklable).

Returns: a Store instance

Sampling helpers for building experiment designs.

#### `rescale_samples(samples: ndarray, ranges: ndarray, *, inplace: bool = False) → ndarray`

Rescale samples from the unit interval [0, 1] to parameter ranges.

**Parameters:**

- **samples** – Array of shape (n, d) drawn from the unit interval.
- **ranges** – Array of shape (d, 2) giving `[[min, max], ...]` per parameter.
- **inplace** – If True, `samples` is overwritten with the result; if False (default), a new array is returned.

**Returns:**

The rescaled samples, shape (n, d).

## Storing results

Storage for parameter sweeps.

#### `class Status(*values)`

Enumeration for scenario run status.

#### `class RunId(scenario_id: int, replication_id: int)`

Identifier for a specific scenario replication combination.

#### `class RunRecord(scenario: Scenario, status: Status = Status.PENDING, output: dict[str, pd.DataFrame] | None = None, failure: FailureInfo | None = None)`

All state associated with a single run.

#### `class Writer(*args, **kwargs)`

Worker-side handle that produces references.

Picklable; carries only configuration, never the store’s durable record. This is the ONLY store capability a worker receives.

#### `to_reference(run_id: RunId, outcome: dict[str, Any]) → Reference`

Persist a run’s outcome and return a reference to it.

#### `class Store(*args, **kwargs)`

The Store interface.

#### `writer() → Writer`

Return the pickleable, write-only handle to hand to workers.

#### `retrieve_output(run_id: RunId) → dict[str, DataFrame]`

Resolve a reference back to its outcome.

#### `write_scenarios(scenarios: list[Scenario]) → None`

Record the full ensemble of scenarios before dispatch.

It is critical that this method is called prior to executing any runs, because mark_succeeded and mark_failed will check against the registered runs.

#### `read_scenarios() → list[Scenario]`

Return the recorded scenarios.

#### `mark_succeeded(ref: Reference) → None`

Record that a run completed and its outcome was received.

For a run to be marked, the scenario should first have been registered via write_scenarios.

#### `mark_failed(run_id: RunId, failure: FailureInfo) → None`

Record that a run failed, with its origin and diagnostics.

For a run to be marked, the scenario should first have been registered via write_scenarios.

#### `mark_aborted(run_id: RunId, failure: FailureInfo) → None`

Record that a run was aborted (e.g. because the executor pool broke).

For a run to be marked, the scenario should first have been registered via write_scenarios.

#### `status() → DataFrame`

One row per scenario: pending / succeeded / failed.

#### `check_status(run_id: RunId) → Status`

Check the status of the run id.

#### `succeeded() → dict[RunId, RunRecord]`

Return all succeeded RunIds and their run record.

#### `failed() → dict[RunId, RunRecord]`

Return all failed RunIds and their run record.

#### `pending() → dict[RunId, RunRecord]`

Return all pending RunIds and their run record.

#### `aborted() → dict[RunId, RunRecord]`

Return all aborted RunIds and their run record.

#### `class Reference(*args, **kwargs)`

A small, picklable handle to a single run’s outcome.

#### `property run_id: RunId`

Return the run_id.

#### `property payload: Any`

Return the payload.

#### `class InMemoryReference(run_id: RunId, payload: dict[str, DataFrame])`

In-memory reference for scenario runs.

#### `class InMemoryWriter`

Writer for in-memory store.

#### `to_reference(run_id: RunId, outcome: dict[str, Any]) → InMemoryReference`

Persist a run’s outcome and return a reference to it.

#### `class InMemoryStore`

Implements in-memory store following the Store protocol.

Initialize in-memory store.

#### `writer() → InMemoryWriter`

Return the pickleable, write-only handle to hand to workers.

#### `retrieve_output(run_id: RunId) → dict[str, DataFrame]`

Retrieve a run’s output.

#### `write_scenarios(scenarios: list[Scenario]) → None`

Record the full ensemble of scenarios before dispatch.

#### `read_scenarios() → list[Scenario]`

Return the recorded scenarios.

#### `mark_succeeded(ref: Reference) → None`

Record that a run completed and its outcome was received.

#### `mark_failed(run_id: RunId, failure: FailureInfo) → None`

Record that a run failed, with its origin and diagnostics.

#### `mark_aborted(run_id: RunId, failure: FailureInfo) → None`

Record that a run was aborted (e.g. because the executor pool broke).

#### `status() → DataFrame`

One row per design point: pending / succeeded / failed.

#### `check_status(run_id: RunId) → Status`

Check the status of a run.

#### `succeeded() → dict[RunId, RunRecord]`

Return all succeeded runs.

#### `failed() → dict[RunId, RunRecord]`

Return all failed runs.

#### `pending() → dict[RunId, RunRecord]`

Return all pending runs.

#### `aborted() → dict[RunId, RunRecord]`

Return all aborted runs.

## Exceptions

Exceptions for the scenarios module.

#### `class FailureOrigin(*values)`

Bases: [`Enum`](https://docs.python.org/3/library/enum.html#enum.Enum)

Enum describing where a scenario run failed.

#### `class FailureInfo(origin: FailureOrigin, exception_type: str, message: str, traceback: str)`

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Structured diagnostics for a failed run.

ensures traceback information can be safely sent from workers to root.

#### `exception RunStageException(message: str)`

Bases: [`ModellyException`](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.exceptions.ModellyException)

Base for failures attributable to a stage of a single run.

Initialize a run-stage exception.

**Parameters:**

**message** – human-readable description of the stage failure. The underlying cause should be attached via `raise ... from e`.

#### `origin: FailureOrigin`

The stage this exception represents. Set by each subclass.

#### `exception ModelInstantiationException(model_class: type, model_args: list[Any], model_kwargs: dict[str, Any], scenario: Scenario)`

Bases: [`RunStageException`](https://remipelloux.github.io/Modelly/apis/scenarios.html#modelly.scenarios.exceptions.RunStageException)

Raised when a model cannot be instantiated for a scenario.

Initialize a model instantiation exception.

**Parameters:**

- **model_class** – the model class that failed to instantiate
- **model_args** – the positional args passed to the model
- **model_kwargs** – the keyword args passed to the model
- **scenario** – the scenario being instantiated

#### `origin: FailureOrigin = 'instantiating'`

The stage this exception represents. Set by each subclass.

#### `exception ModelRunException(run_id: RunId)`

Bases: [`RunStageException`](https://remipelloux.github.io/Modelly/apis/scenarios.html#modelly.scenarios.exceptions.RunStageException)

Raised when a model fails while advancing (run_model).

Initialize a model run exception.

**Parameters:**

**run_id** – identifier of the run that failed during execution

#### `origin: FailureOrigin = 'running'`

The stage this exception represents. Set by each subclass.

#### `exception OutcomeExtractionException(run_id: RunId, outcomes: list[str] | None)`

Bases: [`RunStageException`](https://remipelloux.github.io/Modelly/apis/scenarios.html#modelly.scenarios.exceptions.RunStageException)

Raised when extracting outcomes from a finished model fails.

Initialize an outcome extraction exception.

**Parameters:**

- **run_id** – identifier of the run whose extraction failed
- **outcomes** – the requested outcome keys (None means “all”)

#### `origin: FailureOrigin = 'extracting'`

The stage this exception represents. Set by each subclass.

#### `exception ScenarioNotFoundException(run_id: RunId | None = None)`

Bases: [`ModellyException`](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.exceptions.ModellyException)

Raised when no run is recorded for a given RunId.

Initialize a scenario-not-found exception.

**Parameters:**

**run_id** – the RunId that could not be found, if known

#### `exception ScenarioNotReadyException(run_id: RunId | None = None)`

Bases: [`ModellyException`](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.exceptions.ModellyException)

Raised when a run’s output is requested before it has completed.

Initialize a scenario-not-ready exception.

**Parameters:**

**run_id** – the RunId whose output is not yet available

#### `exception ScenarioFailedException(run_id: RunId | None = None, failure: FailureInfo | None = None)`

Bases: [`ModellyException`](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.exceptions.ModellyException)

Raised when a failed run’s output is requested.

Initialize a scenario-failed exception.

**Parameters:**

- **run_id** – the RunId of the failed run
- **failure** – structured failure diagnostics for the run, if available

#### `exception ScenarioAbortedException(run_id: RunId | None = None, failure: FailureInfo | None = None)`

Bases: [`ModellyException`](https://remipelloux.github.io/Modelly/apis/core.html#modelly.core.exceptions.ModellyException)

Raised when an aborted run’s output is requested.

Initialize a scenario-aborted exception.

**Parameters:**

- **run_id** – the RunId of the aborted run
- **failure** – structured failure diagnostics for the run, if available

## Typed scenarios (2.0, announced)

The 2.0 typed scenarios (epic H5), announced: what 1.5 warns about in a `Scenario` subclass.

In 2.0 a `Scenario` subclass is a typed base: its fields are its annotated attributes, a value of the wrong type is refused, and a parameter it does not declare is an error. 1.5 keeps accepting all three and warns, naming the change to make:

- a public class attribute with no annotation (`beta = 0.3`): 2.0 will not see it as a field; write `beta: float = 0.3`;
- a keyword the subclass does not declare (`MyScenario(betta=0.3)`): 2.0 refuses it; declare it as an annotated field, or fix the name;
- a value whose type does not match a plain annotation (`steps: int` given `"100"`): 2.0 refuses it; pass a value of the annotated type. Only plain classes are checked (`int`, `float`, `bool`, `str`, `tuple`, `list`, `dict`); an `int` is a `float` and a numpy number is the Python number it stands for.

The plain `Scenario(rng=42, density=0.8)` with no subclass stays free-form.

#### `check_call(cls: type, defaults: dict[str, Any], kwargs: dict[str, Any]) → None`

Warn for undeclared keywords and mistyped values of a typed subclass’s instance.

#### `check_class(cls: type) → None`

Warn for each attribute of a new subclass that 2.0 will not see as a field.
