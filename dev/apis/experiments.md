# Experiments

`modelly.experiments` runs parameter studies: a space, a design, replicates and outputs, on any executor, into a resumable Parquet store. How to use it is in [Experiments and sweeps](https://remipelloux.github.io/Modelly/dev/experiments.html).

Module

Contents

modelly.experiments.experiment

Experiment, RunReport, ExperimentError

modelly.experiments.space

ScenarioSpace, Range, Choice, Fixed

modelly.experiments.designs

full factorial, Latin hypercube, Sobol, Halton, custom

modelly.experiments.store

ResultsStore, Results

modelly.experiments.tasks

RunTask, RunOutcome, run_task

modelly.experiments.executors

the registry and the executors

modelly.experiments.spec

TOML experiment files

modelly.experiments.worker

the job-array entry point

## Experiment

`Experiment`: a study (space, design, replicates, outputs) that runs anywhere.

Example

```default
>>> from modelly.experiments import Experiment, ScenarioSpace, designs
>>> experiment = Experiment(
...     model=Epidemic,
...     space=ScenarioSpace(beta=(0.05, 0.5), gamma=(0.05, 0.3), vaccination=[0.0, 0.2]),
...     design=designs.latin_hypercube(200),
...     replicates=20,
...     steps=365,
...     outputs=["infected", "recovered"],
...     store="runs/epidemic",
...     seed=7,
... )
>>> experiment.run(executor="processes", max_parallel=8)
>>> experiment.results().query("SELECT beta, max(infected) FROM runs GROUP BY beta")
```

Every (design point, replicate) gets the SeedSequence child `SeedSequence(seed, spawn_key=(point, replicate))`: its numbers depend on nothing else, so the results are the same on every executor, in any order, and a rerun skips the runs whose seed is already in the store.

#### `exception ExperimentError(outcome: RunOutcome)`

A run failed and the experiment was asked to stop (`on_error="raise"`).

Keep the failed run’s outcome; its traceback is the message.

#### `class RunReport(total: int, skipped: int, done: int = 0, failed: list[RunOutcome] = <factory>)`

What one `Experiment.run` did: runs skipped, finished and failed.

#### `property ok: bool`

Whether no run failed.

#### `add(outcome: RunOutcome) → None`

Count one outcome.

#### `scenario_class(model: type) → type[Scenario] | None`

The Scenario subclass `model`’s `scenario` argument defaults to, if any.

#### `class Experiment(model: type | str, space: ScenarioSpace, design: Design | None = None, replicates: int = 1, steps: int = 100, outputs: str | Iterable[str] | Mapping[str, Any] = (), store: str | Path = 'experiment-results', seed: int = 0, on_error: str = 'record', retries: int = 0)`

A parameter study: every design point, `replicates` times, `steps` steps each.

**Parameters:**

- **model** – the Model class, or `"package.module:Class"` / `"path/model.py:Class"`.
- **space** – the ScenarioSpace (checked against the model’s Scenario class).
- **design** – which points to run (default: a full factorial).
- **replicates** – runs per design point, each with its own seed.
- **steps** – steps per run; a run stops early when `model.running` is False.
- **outputs** – what each step records: attribute or method names, or a mapping of column names to attribute names or functions of the model.
- **store** – the results folder (Parquet files and a DuckDB view).
- **seed** – the experiment’s seed; with it, every run’s seed.
- **on_error** – `"record"` a failed run in the store, `"skip"` it, or `"raise"` an ExperimentError (after recording it).
- **retries** – extra attempts for a failing run before it counts as failed.

Check the study’s definition; nothing runs before `run`.

#### `property points: list[dict[str, Any]]`

The design points, the same for the same seed.

#### `tasks() → list[RunTask]`

One task per (design point, replicate), points first.

#### `pending() → list[RunTask]`

The tasks whose seed has no results in the store yet.

#### `fingerprint() → dict[str, Any]`

What makes two experiments the same (replicates may grow).

#### `run(executor: str | Executor = 'processes', max_parallel: int | None = None, progress: bool | Callable[[int, int, RunOutcome], None] = False, **options: Any) → RunReport`

Run every pending task on `executor`; finished runs are skipped.

`options` go to the executor (`partition=`, `address=`…); `progress=True` shows a bar, a callable gets `(done, total, outcome)`.

#### `results() → Results`

The finished runs: `results().query("SELECT ... FROM runs")`, `.df()`.

#### `failures() → DataFrame`

The recorded failures: run, parameters, attempts and traceback.

## Parameter space

The parameter space of an experiment: ranges, choices and fixed values.

A [`ScenarioSpace`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.space.ScenarioSpace) names every scenario parameter an experiment sets. A `(low, high)` tuple is a [`Range`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.space.Range), a list is a [`Choice`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.space.Choice), anything else is [`Fixed`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.space.Fixed):

```default
space = ScenarioSpace(beta=(0.05, 0.5), n=(50, 200), policy=["none", "lockdown"], width=20)
```

Designs ([`modelly.experiments.designs`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#module-modelly.experiments.designs)) sample the varying dimensions in the unit cube; [`ScenarioSpace.point()`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.space.ScenarioSpace.point) maps one sample to parameter values. [`ScenarioSpace.typed()`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.space.ScenarioSpace.typed) checks the names and types against a Scenario class.

#### `class Range(low: float, high: float, log: bool = False, integer: bool = False)`

A continuous (or integer) interval `[low, high]`, optionally on a log scale.

Example

```default
>>> Range(0.05, 0.5).from_unit(0.5)
0.275
```

#### `from_unit(u: float) → float | int`

The value at position `u` in `[0, 1)` of the interval.

#### `levels(count: int) → list[float | int]`

`count` evenly spaced values from low to high (fewer for a short integer range).

#### `class Choice(values: Sequence[Any])`

One of a list of values, each equally likely under a random design.

Example

```default
>>> Choice(["a", "b"]).from_unit(0.75)
'b'
```

Keep the values as a tuple of plain Python values.

#### `from_unit(u: float) → Any`

The value whose share of `[0, 1)` contains `u`.

#### `levels(count: int | None = None) → list[Any]`

Every value (a factorial design takes them all).

#### `class Fixed(value: Any)`

A value every run takes.

#### `as_dimension(value: Any) → Range | Choice | Fixed`

A Range for a `(low, high)` tuple, a Choice for a list, else Fixed.

#### `class ScenarioSpace(parameters: Mapping[str, Any] | None = None, /, **named: Any)`

Every scenario parameter an experiment sets, varying or fixed.

Example

```default
>>> space = ScenarioSpace(beta=(0.1, 0.3), policy=["a", "b"], n=100)
>>> space.point([0.5, 0.0])
{'beta': 0.2, 'policy': 'a', 'n': 100}
```

Build the space from a mapping and/or keyword arguments.

#### `property names: list[str]`

Every parameter name, in declaration order.

#### `property dimensions: dict[str, Range | Choice]`

The varying parameters (ranges and choices), in declaration order.

#### `property fixed: dict[str, Any]`

The fixed parameters and their values.

#### `point(unit: Sequence[float] | ndarray) → dict[str, Any]`

The parameters at `unit`, one coordinate in `[0, 1)` per dimension.

#### `complete(values: Mapping[str, Any]) → dict[str, Any]`

`values` with the fixed parameters added; unknown names are an error.

#### `typed(scenario: type) → ScenarioSpace`

This space checked against `scenario`’s declared fields and their types.

Unknown names are a ValueError; a range or value of the wrong type is a TypeError. A Range with whole-number bounds over an `int` field becomes an integer Range.

#### `to_dict() → dict[str, Any]`

A JSON-ready description of the space (for the store’s fingerprint).

## Designs

Experimental designs: which points of a ScenarioSpace an experiment runs.

- [`full_factorial()`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.designs.full_factorial): every combination, `levels` values per range;
- [`latin_hypercube()`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.designs.latin_hypercube), [`sobol()`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.designs.sobol), [`halton()`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.designs.halton): `n` points from `scipy.stats.qmc`, scrambled from the experiment’s seed;
- [`custom()`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.designs.custom): a list of points written by hand (or read from a file).

Example

```default
>>> from modelly.experiments import ScenarioSpace, designs
>>> space = ScenarioSpace(beta=(0.1, 0.3), policy=["a", "b"])
>>> len(designs.full_factorial(levels=3).points(space))
6
```

#### `class Design`

Base class: `points(space, rng)` lists the parameter dicts to run.

#### `points(space: ScenarioSpace, rng: Generator | None = None) → list[dict[str, Any]]`

The design’s points in `space`; `rng` scrambles a random design.

#### `to_dict() → dict[str, Any]`

A JSON-ready description of the design.

#### `class FullFactorial(levels: int | Mapping[str, int] = 5)`

Every combination: `levels` evenly spaced values per range, every choice.

#### `points(space: ScenarioSpace, rng: Generator | None = None) → list[dict[str, Any]]`

The Cartesian product of every dimension’s levels, the last varying fastest.

#### `class LatinHypercube(n: int)`

A Latin hypercube: each range cut in `n` strata, one point per stratum.

#### `sampler(dimensions: int, rng: Generator) → QMCEngine`

The scipy LatinHypercube engine.

#### `class Sobol(n: int)`

A scrambled Sobol sequence; balanced when `n` is a power of two.

#### `sampler(dimensions: int, rng: Generator) → QMCEngine`

The scrambled scipy Sobol engine.

#### `class Halton(n: int)`

A scrambled Halton sequence (any `n`).

#### `sampler(dimensions: int, rng: Generator) → QMCEngine`

The scrambled scipy Halton engine.

#### `class Custom(rows: list[dict[str, ~typing.Any]]=<factory>)`

Points given as a list of dicts; the space’s fixed values fill the gaps.

#### `points(space: ScenarioSpace, rng: Generator | None = None) → list[dict[str, Any]]`

The rows, completed with the fixed parameters and checked against the space.

#### `full_factorial(levels: int | Mapping[str, int] = 5) → FullFactorial`

Every combination of `levels` values per range (a mapping sets them per name).

#### `latin_hypercube(n: int) → LatinHypercube`

`n` points of a Latin hypercube.

#### `sobol(n: int) → Sobol`

`n` points of a scrambled Sobol sequence (use a power of two).

#### `halton(n: int) → Halton`

`n` points of a scrambled Halton sequence.

#### `custom(rows: Sequence[Mapping[str, Any]]) → Custom`

The points in `rows`, one dict of parameter values each.

#### `design_kinds() → list[str]`

Every design kind: the built-in ones and the `modelly.samplers` plugins.

#### `design_factory(kind: str) → Callable[[...], Design]`

The factory of design `kind`, built in or from a `modelly.samplers` plugin.

**Raises:**

- [**KeyError**](https://docs.python.org/3/builtins/exceptions.html#KeyError) – when no design has that kind.
- [**PluginError**](https://remipelloux.github.io/Modelly/dev/apis/plugins.html#modelly.plugins.PluginError) – when the plugin fails to load.

## Results store

The results store: one Parquet file per finished run, a DuckDB view over them all.

Layout of a store folder:

```default
experiment.json          what the experiment is (model, design, seed...)
run-<seed>.parquet       one finished run: one row per step
failures/run-<seed>.json a run that raised, with its traceback
```

Every file is written to a temporary name and moved into place with `os.replace`, so a killed sweep leaves only whole files and is resumed by skipping the seeds already present. Rows have the columns of `KEYS`, the parameters, `step` and the outputs.

#### `exception StoreMismatchError`

The store folder holds the results of a different experiment.

#### `write_text_atomic(path: Path, text: str) → None`

Write `text` to `path` (UTF-8) through a temporary file and `os.replace`.

#### `class ResultsStore(path: str | Path)`

A folder of per-run Parquet files, append-only and resumable.

Example

```default
>>> store = ResultsStore("runs/epidemic")
>>> store.finished()  # the seeds already run
```

Use (and create on first write) the folder `path`.

#### `run_path(seed: int) → Path`

The Parquet file of the run with `seed`.

#### `failure_path(seed: int) → Path`

The failure record of the run with `seed`.

#### `finished() → set[int]`

The seeds of every run with a results file.

#### `write_run(seed: int, table: Any) → Path`

Store a finished run’s `pyarrow.Table`; clear any earlier failure record.

#### `record_failure(seed: int, record: dict[str, Any]) → None`

Keep a failed run’s details (error, traceback, attempts) as JSON.

#### `failed() → set[int]`

The seeds of every run with a failure record.

#### `failures() → DataFrame`

One row per recorded failure, in seed order.

#### `claim(fingerprint: dict[str, Any]) → None`

Record what experiment writes here; refuse a store holding another one.

#### `results() → Results`

The finished runs, as a DuckDB view named `runs`.

#### `class Results(store: ResultsStore)`

SQL over a store’s runs: `query` returns a DuckDB relation.

Example

```default
>>> results.query("SELECT beta, avg(infected) FROM runs GROUP BY beta").df()
```

Open an in-memory DuckDB connection with the view `runs` over the store.

#### `query(sql: str) → duckdb.DuckDBPyRelation`

Run `sql` (which reads the view `runs`); a DuckDB relation.

#### `property relation: duckdb.DuckDBPyRelation`

Every row, ordered by point, replicate and step.

#### `df() → DataFrame`

Every row as a pandas DataFrame, ordered by point, replicate and step.

#### `arrow() → pa.Table`

Every row as a `pyarrow.Table`, ordered by point, replicate and step.

## Runs

One run of an experiment: the task a worker receives and the function it calls.

A [`RunTask`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.tasks.RunTask) holds only plain values (the model as an import path, the parameters, the seed’s entropy and spawn key), so it pickles for processes, Dask and Ray, and serialises to JSON for SLURM and PBS job arrays. Workers started with `spawn` import the model by that path; nothing is inherited.

The run’s generator comes from `SeedSequence(entropy, spawn_key=(point, replicate))`: the same numbers whatever executor, worker or order runs it.

#### `reference(obj: Any) → str`

`module:qualname` of a class or function; a script’s `__main__` becomes its path.

#### `spawn_safe(ref: str) → bool`

Whether a fresh process can import `ref` (not a notebook, lambda or closure).

#### `resolve(ref: str) → Any`

The object `ref` names, imported on first use in this process.

#### `run_seed(entropy: int, point: int, replicate: int) → int`

The integer seed recorded for a run (and the key resume works by).

#### `class RunTask(model: str, params: dict[str, Any], point: int, replicate: int, entropy: int, steps: int, outputs: dict[str, str], store: str, retries: int = 0, record_failures: bool = True)`

Everything one worker needs to run one (design point, replicate).

#### `property seed: int`

a function of the experiment seed, point and replicate.

**Type:**

This run’s seed

#### `property run_id: str`

`<point>-<replicate>`.

#### `seed_sequence() → SeedSequence`

The SeedSequence child of this (point, replicate).

#### `to_dict() → dict[str, Any]`

The task as JSON-ready values.

#### `classmethod from_dict(data: Mapping[str, Any]) → RunTask`

The task [`to_dict()`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.tasks.RunTask.to_dict) wrote.

#### `class RunOutcome(run_id: str, seed: int, status: str, attempts: int = 1, error: str | None = None)`

What a worker reports back: the run, its status and the error if it failed.

#### `simulate(task: RunTask) → Any`

Build the model, step it `task.steps` times and return the rows as a pyarrow Table.

Row 0 is the state after construction; the run stops early when `model.running` becomes False.

#### `run_task(task: RunTask) → RunOutcome`

Run `task` (retrying `task.retries` times), store it, report the outcome.

The function every executor calls; it never raises for a model error.

## Executors

Executors: where an experiment’s runs execute, chosen by name.

serial

in this process, one run after another

threads

a thread pool (parallel on free-threaded Python builds)

processes

a process pool started with forkserver or spawn

dask

a dask.distributed cluster (a local one by default)

ray

a Ray cluster (modelly-abm[ray])

slurm

a SLURM job array submitted with sbatch

pbs

a PBS job array submitted with qsub

Every executor calls [`modelly.experiments.tasks.run_task()`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.tasks.run_task) once per run and yields its [`RunOutcome`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.tasks.RunOutcome); the worker writes the run’s Parquet file itself, so the results never depend on the executor. A plugin adds an executor through the `modelly.executors` entry point group (`name = "package.module:ExecutorClass"`) or [`register_executor()`](https://remipelloux.github.io/Modelly/dev/apis/experiments.html#modelly.experiments.executors.register_executor).

#### `class Executor(**options: Any)`

Base class: `run(tasks, max_parallel)` yields one outcome per task.

`in_process` executors share this interpreter, so they can run models and outputs a fresh process could not import (a notebook class, a lambda).

Keep the executor’s options; unknown ones are an error.

#### `run(tasks: Sequence[RunTask], max_parallel: int | None = None) → Iterator[RunOutcome]`

Run every task, yielding each outcome as it finishes.

#### `check(tasks: Sequence[RunTask]) → None`

Refuse tasks naming a model or output a worker process cannot import.

#### `available_executors() → list[str]`

Every executor name: built-in, registered and from entry points.

#### `get_executor(executor: str | Executor, **options: Any) → Executor`

An executor instance from its name (with `options`) or as given.

Example

```default
>>> get_executor("threads").name
'threads'
```

#### `register_executor(name: str, factory: Callable[[...], Executor]) → None`

Make `factory(**options)` available as `executor=name`.

Executors on this machine: serial, a thread pool and a process pool.

The process pool starts its workers with `forkserver` where it exists and `spawn` elsewhere (Windows, macOS), as `modelly.batch.run_batch` does: each worker imports the model by its module path, so the same script runs on every platform. Scripts need the usual `if __name__ == "__main__":` guard.

#### `class SerialExecutor(**options: Any)`

Every run in this process, in task order.

Keep the executor’s options; unknown ones are an error.

#### `run(tasks: Sequence[RunTask], max_parallel: int | None = None) → Iterator[RunOutcome]`

Run the tasks one after another.

#### `class ThreadExecutor(**options: Any)`

A thread pool: parallel on free-threaded Python, concurrent otherwise.

Keep the executor’s options; unknown ones are an error.

#### `run(tasks: Sequence[RunTask], max_parallel: int | None = None) → Iterator[RunOutcome]`

Run the tasks on up to `max_parallel` threads.

#### `class ProcessExecutor(**options: Any)`

A pool of worker processes that import the model (spawn-safe).

Keep the executor’s options; unknown ones are an error.

#### `run(tasks: Sequence[RunTask], max_parallel: int | None = None) → Iterator[RunOutcome]`

Run the tasks on up to `max_parallel` processes.

The Dask executor: runs on a `dask.distributed` cluster.

With no `address` or `client` it starts a local cluster of worker processes (one thread each, no dashboard, bound to 127.0.0.1) and closes it afterwards; with one, it uses that cluster and leaves it running. Workers import the model by its module path, and write the run’s Parquet file to the store themselves, so the store must be on a filesystem they share. Needs `pip install "modelly-abm[dask]"`.

#### `class DaskExecutor(address: str | None = None, client: Any = None, **cluster_options: Any)`

Runs on a Dask cluster, at most `max_parallel` runs in flight.

**Parameters:**

- **address** – a scheduler address to connect to.
- **client** – an existing `distributed.Client` (kept open).
- ****cluster_options** – extra `LocalCluster` arguments for the local cluster.

Example

```default
>>> experiment.run(executor="dask", address="tcp://scheduler:8786")
```

Keep where to connect; nothing starts before `run`.

#### `run(tasks: Sequence[RunTask], max_parallel: int | None = None) → Iterator[RunOutcome]`

Submit the tasks, keeping `max_parallel` in flight; yield outcomes.

The Ray executor: runs on a Ray cluster through its public task API.

`ray.init` is called when Ray is not initialised yet (a local cluster with no `address`) and `ray.shutdown` afterwards; an initialised Ray is used as it is and left running. Workers import the model by its module path and write the run’s Parquet file themselves, so the store must be on a shared filesystem. Needs `pip install "modelly-abm[ray]"`.

#### `class RayExecutor(address: str | None = None, **init_options: Any)`

Runs each task as a Ray remote function, at most `max_parallel` in flight.

**Parameters:**

- **address** – the cluster to join (`"auto"`, `"ray://host:10001"`…); `None` starts a local Ray.
- ****init_options** – extra `ray.init` arguments (`num_cpus`, `runtime_env`…).

Example

```default
>>> experiment.run(executor="ray", address="auto")
```

Keep where to connect; nothing starts before `run`.

#### `run(tasks: Sequence[RunTask], max_parallel: int | None = None) → Iterator[RunOutcome]`

Submit the tasks, keeping `max_parallel` in flight; yield outcomes.

SLURM and PBS executors: one job array per experiment, submitted with `sbatch` or `qsub`.

`run` writes, in `<store>/jobs/<id>/`, a `tasks.json` (one task per array element) and a `job.sh` whose every element runs `python -m modelly.experiments.worker tasks.json $INDEX`, then submits the script. The store must be on a filesystem the compute nodes share; workers write each run’s Parquet file there. With `wait=True` the executor polls the store until every run has finished or failed; otherwise `run` returns once the job is submitted and the results appear as the array runs (rerunning the experiment skips what is finished, so it doubles as “collect”).

Only `sbatch` / `qsub` are called (found on `PATH`); the scripts are bash for the Linux nodes and written with Unix line endings from any OS.

#### `class ClusterExecutor(job_name: str = 'modelly', queue: str | None = None, account: str | None = None, walltime: str | None = None, memory: str | None = None, cpus: int = 1, directives: Sequence[str] = (), setup: Sequence[str] = (), python: str = 'python3', wait: bool = False, poll_interval: float = 30.0, timeout: float | None = None, submit_command: str | None = None)`

A job array on a batch scheduler; subclasses set the directives.

**Parameters:**

- **job_name** – the scheduler’s job name.
- **queue** – the partition (SLURM) or queue (PBS).
- **account** – the account or project charged.
- **walltime** – the time limit of one array element (`"01:00:00"`).
- **memory** – memory per element (`"4G"` / `"4gb"`).
- **cpus** – CPUs per element.
- **directives** – extra scheduler lines, without the `#SBATCH`/`#PBS` prefix.
- **setup** – shell lines run before the worker (`module load python`…).
- **python** – the Python on the compute nodes.
- **wait** – poll the store until every run has finished or failed.
- **poll_interval** – seconds between polls; `timeout`: give up after (seconds).
- **submit_command** – the submit program (default: found on `PATH`).

Keep the job’s settings; nothing is written before `run`.

#### `scheduler_lines(count: int, limit: int | None, folder: Path) → list[str]`

The scheduler directives (without prefix) for `count` elements.

#### `script(tasks_file: Path, count: int, limit: int | None) → str`

The job script running element `$INDEX` of `tasks_file`.

#### `submit(script: Path) → str`

Submit `script`; the scheduler’s job id.

#### `job_id_from(output: str) → str`

The job id in the submit command’s output.

#### `run(tasks: Sequence[RunTask], max_parallel: int | None = None) → Iterator[RunOutcome]`

Write the job files, submit the array and, with `wait`, poll the store.

#### `prepare(tasks: Sequence[RunTask], limit: int | None, folder: Path) → Path`

Write `tasks.json` and `job.sh` in `folder`; the script’s path.

#### `poll(tasks: Sequence[RunTask], store: ResultsStore) → Iterator[RunOutcome]`

Yield each task’s outcome as its result or failure file appears.

#### `class SlurmExecutor(job_name: str = 'modelly', queue: str | None = None, account: str | None = None, walltime: str | None = None, memory: str | None = None, cpus: int = 1, directives: Sequence[str] = (), setup: Sequence[str] = (), python: str = 'python3', wait: bool = False, poll_interval: float = 30.0, timeout: float | None = None, submit_command: str | None = None)`

A SLURM job array (`sbatch --parsable`), `%max_parallel` elements at a time.

Example

```default
>>> experiment.run(executor="slurm", queue="short", max_parallel=500)
```

Keep the job’s settings; nothing is written before `run`.

#### `scheduler_lines(count: int, limit: int | None, folder: Path) → list[str]`

–job-name, –array, –output and the resources set.

#### `job_id_from(output: str) → str`

`--parsable` prints `jobid[;cluster]`.

#### `class PBSExecutor(job_name: str = 'modelly', queue: str | None = None, account: str | None = None, walltime: str | None = None, memory: str | None = None, cpus: int = 1, directives: Sequence[str] = (), setup: Sequence[str] = (), python: str = 'python3', wait: bool = False, poll_interval: float = 30.0, timeout: float | None = None, submit_command: str | None = None)`

A PBS Pro job array (`qsub -J`), with `max_run_subjobs` as the throttle.

Example

```default
>>> experiment.run(executor="pbs", queue="workq", walltime="02:00:00")
```

Keep the job’s settings; nothing is written before `run`.

#### `scheduler_lines(count: int, limit: int | None, folder: Path) → list[str]`

-N, -J, -j oe, -o and the resources set.

## Experiment files and the worker

Read an experiment from a TOML file (what `modelly experiment run spec.toml` runs).

Example spec:

```default
[experiment]
model = "model.py:Epidemic"     # relative to this file, or package.module:Class
steps = 365
replicates = 20
seed = 7
outputs = ["infected", "recovered"]
store = "runs/epidemic"         # relative to this file
on_error = "record"             # or "skip", "raise"
retries = 1

[space]
beta = { min = 0.05, max = 0.5 }          # a range (log = true, integer = true)
vaccination = [0.0, 0.2, 0.4]             # a choice
population = 10000                        # a fixed value

[design]
kind = "latin_hypercube"        # full_factorial (levels), sobol, halton (n), custom (points)
n = 200

[run]
executor = "processes"
max_parallel = 8
[run.options]                   # passed to the executor (queue, walltime, address...)
```

#### `exception SpecError`

The experiment file is missing a value or has one of the wrong kind.

#### `class RunSettings(executor: str = 'processes', max_parallel: int | None = None, options: dict[str, ~typing.Any]=<factory>)`

The `[run]` table: executor, parallelism and executor options.

#### `relative_path(path: str, base: Path) → str`

`path` resolved against the spec’s folder unless absolute.

#### `model_reference(target: str, base: Path) → str`

The model reference, a `.py` source made relative to the spec’s folder.

#### `read_document(path: str | Path) → tuple[dict[str, Any], Path]`

The parsed TOML file and the folder its relative paths start from.

#### `read_space(document: Mapping[str, Any]) → ScenarioSpace`

The `[space]` table as a ScenarioSpace.

#### `read_run(document: Mapping[str, Any], executor: str = 'processes') → RunSettings`

The `[run]` table; `executor` when it names none.

#### `load_spec(path: str | Path) → tuple[Experiment, RunSettings]`

The Experiment a TOML file describes, and its `[run]` settings.

The job-array task entry point: `python -m modelly.experiments.worker TASKS [INDEX]`.

`TASKS` is the `tasks.json` a SLURM or PBS executor wrote; `INDEX` picks one task from it (default: `$SLURM_ARRAY_TASK_ID`, `$PBS_ARRAY_INDEX` or `$PBS_ARRAYID`). The task runs, its Parquet file goes to the store, and the exit status is 0 when it finished, 1 when it failed (recorded in the store).

#### `load_tasks(path: str | Path) → list[RunTask]`

The tasks a cluster executor wrote to `path`.

#### `array_index(argument: str | None = None) → int`

The task index: `argument`, else the scheduler’s array index variable.

#### `run_array_task(tasks_file: str | Path, index: int) → RunOutcome`

Run task `index` of `tasks_file` (what each job-array element does).

#### `main(argv: list[str] | None = None) → int`

Run one task of a job array; the exit status.
