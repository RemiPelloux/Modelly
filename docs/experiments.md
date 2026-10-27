# Experiments and sweeps

`modelly.experiments` describes a study in one object (the model, a parameter space, a design,
replicates, steps and outputs) and runs it on this machine, on a Dask or Ray cluster, or as a
SLURM or PBS job array. Every run writes its own Parquet file to a results folder, so a sweep
that is interrupted resumes where it stopped, and the results are queried with SQL through
DuckDB without loading them all into memory.

The store needs `pyarrow` and `duckdb`:

```bash
pip install "modelly-abm[experiments]"   # add [dask] or [ray] for those executors
```

## A first experiment

```python
from modelly.examples.basic.boltzmann_wealth_model.model import BoltzmannWealth
from modelly.experiments import Experiment, ScenarioSpace, designs

experiment = Experiment(
    model=BoltzmannWealth,
    space=ScenarioSpace(n=(50, 200), width=[10, 20], height=10),
    design=designs.latin_hypercube(8),
    replicates=3,
    steps=20,
    outputs=["gini"],
    store="runs/boltzmann",
    seed=42,
)

if __name__ == "__main__":  # process workers re-import this script on Windows and macOS
    report = experiment.run(executor="processes", max_parallel=4)
    print(report)  # RunReport(total=24, skipped=0, done=24, failed=[])

    sql = "SELECT width, avg(gini) FROM runs WHERE step = 20 GROUP BY width ORDER BY width"
    print(experiment.results().query(sql).df())
```

Each of the 8 design points runs 3 times with its own seed, for 20 steps; `gini` is read after
construction (step 0) and after every step. Running the script again does nothing: all 24 runs
are already in `runs/boltzmann`.

## The parameter space

`ScenarioSpace` names the scenario parameters the experiment sets:

| Written as | Becomes | Meaning |
|---|---|---|
| `beta=(0.05, 0.5)` | `Range(0.05, 0.5)` | any value in the interval |
| `n=(50, 200)` | `Range(50, 200, integer=True)` | a whole number in the interval |
| `rate=Range(1e-4, 1e-1, log=True)` | | an interval on a log scale |
| `policy=["none", "lockdown"]` | `Choice([...])` | one of the values |
| `height=10` | `Fixed(10)` | the same value for every run |

When the model's `scenario` argument defaults to a `Scenario` subclass, the space is checked
against it before anything runs: a name the scenario does not declare is a `ValueError`, and a
value of the wrong type (a fractional range for an `int` field, a number for a `str` field) is a
`TypeError`. A range over a `float` field is continuous even when written with whole numbers,
`(0, 1)`. A model without a Scenario class receives the parameters as constructor arguments.

## Designs

| Design | Points | Notes |
|---|---|---|
| `designs.full_factorial(levels=5)` | every combination | `levels` evenly spaced values per range (a dict sets them per name), every choice |
| `designs.latin_hypercube(n)` | `n` | each range cut in `n` strata, one point in each |
| `designs.sobol(n)` | `n` | scrambled Sobol sequence; balanced when `n` is a power of two (scipy warns otherwise) |
| `designs.halton(n)` | `n` | scrambled Halton sequence, any `n` |
| `designs.custom(rows)` | `len(rows)` | your own list of dicts; the fixed values fill the gaps |

The sampled designs come from `scipy.stats.qmc`, scrambled from the experiment's seed: the same
seed gives the same points. A choice takes its share of the unit interval, so a Latin hypercube
over a choice of two values puts half its points on each.

## Outputs

`outputs` lists what each step records:

- an attribute, property or method of the model: `"gini"`, `"infected"` (a method is called);
- a dotted path: `"scenario.beta"`, `"grid.width"`;
- a mapping of column names to either of the above, or to a function of the model:
  `{"peak": "peak_infected", "share": share_infected}`.

Each value must be a number, a boolean or a string. A function given for the process, Dask, Ray
or cluster executors must be defined at module level in an importable file, like the model.

## Seeds and reproducibility

The experiment's `seed` is the root of a `numpy.random.SeedSequence`. Run `(point,
replicate)` uses the child `SeedSequence(seed, spawn_key=(point, replicate))`, the same stream
`SeedSequence(seed).spawn(...)[point].spawn(...)[replicate]` gives. The child seeds the
scenario, so both `model.rng` and `model.random` follow from it. A run's numbers therefore depend
on nothing but its parameters and that child: the same experiment gives identical results on the
serial, thread, process, Dask, Ray and cluster executors, with any number of workers, in any
order. The test suite checks this for serial, threads, processes and a local Dask cluster.

## The results store

The store is a folder:

```text
runs/boltzmann/
  experiment.json              what the experiment is (model, points, steps, outputs, seed)
  run-<seed>.parquet           one finished run, one row per step
  failures/run-<seed>.json     a run that raised: parameters, attempts, traceback
  jobs/<id>/                   tasks.json and job.sh of a SLURM or PBS submission
```

Every row has these columns, in this order:

| Column | Content |
|---|---|
| `run_id` | `"<point>-<replicate>"` |
| `point` | index of the design point |
| `replicate` | index of the replicate |
| `seed` | the run's integer seed (derived from the child SeedSequence) |
| one per parameter | the run's parameter values, fixed ones included |
| `step` | 0 after construction, then 1, 2, ... |
| one per output | the recorded values |

Files are written to a temporary name and moved into place with `os.replace`, so a reader never
sees half a file, on Windows, macOS and Linux alike. Nothing is ever rewritten: the store only
grows.

`experiment.results()` opens an in-memory DuckDB connection with a view `runs` over every file:

```python
results = experiment.results()
results.query("SELECT point, max(gini) AS peak FROM runs GROUP BY point").df()
results.df()  # everything, ordered by point, replicate and step
results.arrow()  # the same as a pyarrow Table
len(results)  # rows
```

The files are ordinary Parquet: pandas, polars, R (`arrow::open_dataset`) and Julia read the
folder directly.

## Resuming and failures

A rerun of the same experiment skips every run whose seed already has a file, so a sweep that was
killed, or a machine that restarted, continues where it stopped. `experiment.json` guards the
folder: running a different experiment (another seed, design, model, steps or outputs) into it
raises `StoreMismatchError`. Raising `replicates` is allowed and runs only the new replicates.

A run that raises is handled by `on_error`:

| `on_error` | What happens |
|---|---|
| `"record"` (default) | the traceback goes to `failures/`; the sweep goes on |
| `"skip"` | nothing is written; the sweep goes on |
| `"raise"` | the failure is recorded, then `ExperimentError` stops the sweep |

`retries=2` gives a failing run two more attempts first. A failed run has no results file, so the
next rerun tries it again; `experiment.failures()` lists the recorded ones as a DataFrame.
`run()` returns a `RunReport` with `total`, `skipped`, `done` and `failed`; `progress=True`
shows a progress bar, and a function `progress(done, total, outcome)` is called after each run.

## Executors

| `executor=` | Runs on | Options |
|---|---|---|
| `"serial"` | this process, in order | |
| `"threads"` | a thread pool; parallel on free-threaded Python | |
| `"processes"` (default) | worker processes started with `forkserver` or `spawn` | |
| `"dask"` | a `dask.distributed` cluster | `address=`, `client=`, `LocalCluster` arguments |
| `"ray"` | a Ray cluster | `address=`, `ray.init` arguments |
| `"slurm"` | a SLURM job array | see [Running on a cluster](#running-on-a-cluster) |
| `"pbs"` | a PBS Pro job array | the same |

`max_parallel` caps the runs in flight. Options go to `run()` as keywords
(`experiment.run("dask", address="tcp://10.0.0.5:8786")`), or build the executor yourself
(`experiment.run(SlurmExecutor(queue="short"))`).

Process, Dask, Ray and cluster workers start fresh and import the model by its module path,
which is what makes them work on Windows and macOS (where processes are spawned, not forked) and
on other machines. The model and any output function must therefore live in an importable file;
a class defined in a notebook runs on `"serial"` or `"threads"`, and the other executors refuse it
with a message saying so. A script that runs an experiment on processes needs the
`if __name__ == "__main__":` guard.

New executors are plugins: a package declares an entry point in the group `modelly.executors`
(`myexec = "mypackage.module:MyExecutor"`), where `MyExecutor` subclasses
`modelly.experiments.Executor` and implements `run(tasks, max_parallel)`, yielding the
`RunOutcome` of `modelly.experiments.tasks.run_task(task)` for every task.
`register_executor(name, factory)` does the same at run time.

## From the command line

An experiment can live in a TOML file:

```toml
[experiment]
model = "model.py:Epidemic"           # relative to this file, or package.module:Class
steps = 365
replicates = 20
seed = 7
outputs = ["infected", "recovered"]
store = "runs/epidemic"                # relative to this file
on_error = "record"
retries = 1

[space]
beta = { min = 0.05, max = 0.5 }       # a range; add log = true or integer = true
gamma = { min = 0.05, max = 0.3 }
vaccination = [0.0, 0.2, 0.4]          # a choice
population = 10000                     # a fixed value

[design]
kind = "latin_hypercube"               # full_factorial (levels), sobol, halton (n), custom (points)
n = 200

[run]
executor = "processes"
max_parallel = 8
[run.options]                          # passed to the executor
```

```bash
modelly experiment run study.toml                      # run what is pending
modelly experiment run study.toml --executor threads --max-parallel 4
modelly experiment run study.toml --dry-run            # list the pending runs
modelly experiment status study.toml                   # finished, failed, pending
```

`python -m modelly.experiments` is the same command. Exit status: 0 when every run finished,
1 when at least one failed, 2 for a bad command line, an unreadable spec, or a store that holds
another experiment. `modelly experiment --help` shows the whole reference.

## Running on a cluster

This section is the research software engineer's guide: the same experiment as on a laptop, with
one line changed, and the same numbers.

**What the SLURM and PBS executors do.** `run()` writes, in `<store>/jobs/<id>/`, a `tasks.json`
holding one task per pending run and a bash `job.sh`, then submits the script once with `sbatch
--parsable` or `qsub`. Each array element runs `python -m modelly.experiments.worker tasks.json
$INDEX`, which builds the model, runs it and writes its Parquet file to the store. Only those two
commands are called; the files are written with Unix line endings from any operating system.

**Before you submit.**

1. Put the store on a filesystem every compute node sees (home or project space, not `/tmp`).
2. Install the same Modelly and model code on the nodes, and make the model importable there:
   a package installed in the environment, or a path such as `model = "/project/study/model.py:Epidemic"`.
3. Submit from the login node, where `sbatch` or `qsub` is on `PATH` (or pass `submit_command=`).

**SLURM.**

```python
from modelly.experiments.executors.cluster import SlurmExecutor

executor = SlurmExecutor(
    queue="short",  # --partition
    account="my-project",  # --account
    walltime="HH:MM:SS",  # --time, for one run
    memory="4G",  # --mem
    setup=["module load python", "source ~/venvs/study/bin/activate"],
    python="python3",  # the Python on the nodes
)
experiment.run(executor, max_parallel=200)  # --array=0-N%200
```

or, in the spec, `executor = "slurm"` with the same keys under `[run.options]`. `directives=`
adds raw `#SBATCH` lines (`["--qos=normal", "--constraint=skylake"]`).

**PBS Pro.** `PBSExecutor` takes the same arguments; `queue` becomes `-q`, `account` `-A`,
`walltime` and `memory` `-l`, the array is `-J 0-N` and `max_parallel` becomes
`-W max_run_subjobs`.

**Waiting or collecting.** By default `run()` returns as soon as the array is submitted, with
`done=0` in its report. The results appear in the store as elements finish; at any time,
`modelly experiment status study.toml` counts them and `experiment.results()` queries what is
there. Running the experiment again submits only what is not finished, so after a node failure
or a time limit, resubmitting is the same command. With `wait=True` (and `poll_interval=`,
`timeout=` in seconds) the call instead polls the store and reports each run as it finishes or
fails.

**Dask and Ray clusters.** On a cluster running a Dask scheduler (for example through
`dask-jobqueue`), pass its address: `experiment.run("dask", address="tcp://node:8786")`; for
Ray, `experiment.run("ray", address="auto")`. The same rules apply: a shared store and an
importable model.

**Checking reproducibility.** Run a few design points on your laptop with `"serial"` into one
store and the full experiment on the cluster into another, then compare the rows of the common
seeds: they are identical, because every run's stream comes from its own `SeedSequence` child.

## Exporting a DataCollector

`DataCollector` writes Arrow tables and Parquet files directly, atomically like the store:

```python
model.datacollector.to_parquet("out/model.parquet")  # model reporters
# agent reporters, with Step and AgentID columns
model.datacollector.to_parquet("out/agents.parquet", kind="agent")
table = model.datacollector.to_arrow("table", name="trades")  # a pyarrow Table

from modelly.data.io import query, tables_of

query("SELECT avg(Gini) FROM model", **tables_of(model.datacollector)).df()
query("SELECT count(*) FROM runs", runs="out/*.parquet").fetchall()
```

`query` registers Arrow tables, DataFrames and Parquet paths or globs under the names you give
and returns a DuckDB relation.

For gridded time series, `to_xarray` gives an `xarray.Dataset` with a `time` dimension
(`pip install "modelly-abm[xarray]"`; xarray is imported only then). A model reporter that
returns a number is a series over `time`; one that returns an array of the same shape every
step, such as a property layer's grid, is stacked into `(time, ...)`. Agent reporters become a
`(time, AgentID)` panel, NaN where an agent did not exist, so the two datasets of one run merge:

```python
import xarray as xr

grid = model.datacollector.to_xarray(dims={"heat": ("x", "y")})  # heat: (time, x, y)
grid["heat"].isel(time=-1).plot()
agents = model.datacollector.to_xarray("agent")  # (time, AgentID)
xr.merge([grid, agents]).to_netcdf("run.nc")  # netCDF for R, Julia, Panoply, CDO
```

Without `dims`, the extra dimensions are named `heat_dim0`, `heat_dim1`; `kind="agenttype"`
with `name=` the agent class gives one class's reporters. See [From R and Julia](r_and_julia.md)
for reading the Parquet and netCDF files outside Python.
