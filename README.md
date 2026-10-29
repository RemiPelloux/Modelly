<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/RemiPelloux/Modelly/main/docs/images/branding/banner-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/RemiPelloux/Modelly/main/docs/images/branding/banner-light.svg">
    <img src="https://raw.githubusercontent.com/RemiPelloux/Modelly/main/docs/images/branding/banner-light.svg" alt="Modelly: agent-based modeling in Python" width="100%">
  </picture>
</p>

<p align="center">
  <a href="#development"><img src="https://raw.githubusercontent.com/RemiPelloux/Modelly/main/docs/images/badges/coverage.svg" alt="coverage"></a>
  <a href="https://pypi.org/project/modelly-abm/"><img src="https://img.shields.io/pypi/v/modelly-abm?color=0F766E&label=pypi" alt="PyPI version"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-3B82F6" alt="python 3.12+">
  <img src="https://img.shields.io/badge/ruff-linted-261230" alt="ruff">
  <a href="https://github.com/RemiPelloux/Modelly/blob/main/pelloux-guidelines.md"><img src="https://img.shields.io/badge/code%20discipline-Pelloux-0F766E" alt="Pelloux guidelines"></a>
  <a href="https://github.com/RemiPelloux/Modelly/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-4C9A2A" alt="license: Apache-2.0"></a>
</p>

<h1 align="center">Modelly: agent-based modeling in Python</h1>

<p align="center"><b>Modelly</b> is an <b>agent-based modeling (ABM)</b> framework for Python. Declare a
typed scenario, give your agents behaviour, run the world forward in time, then measure, replay and
publish it. Seeded runs, numpy-backed agents, grids, networks and continuous space, discrete-event
time, pandas data collection, browser visualization. Fast by construction, reproducible by default.</p>

<p align="center">
  <a href="https://remipelloux.github.io/Modelly/">Documentation</a> ·
  <a href="https://remipelloux.github.io/Modelly/getting_started.html">Tutorials</a> ·
  <a href="#built-in-examples">Examples</a> ·
  <a href="#coming-from-mesa">Coming from Mesa</a> ·
  <a href="https://github.com/RemiPelloux/Modelly/blob/main/CHANGELOG.md">Changelog</a> ·
  <a href="https://remipelloux.github.io/Modelly/roadmap/">Roadmap</a>
</p>

---

**Status:** stable, Python 3.12+, release 1.4.0. Every public name has a stability level
(`docs/api_stability.toml`): stable names follow semantic versioning and the deprecation policy;
the newest packages are marked provisional. The current version is `modelly.__version__`.

```bash
pip install modelly-abm
python -c "import modelly; print(modelly.__version__)"   # the import name is modelly
```

Then run the [wealth-exchange example](https://github.com/RemiPelloux/Modelly/blob/main/example.py),
which prints its Gini coefficient.

## Vision

Agent-based models are how researchers study systems whose behaviour emerges from many
interacting parts: markets, epidemics, ecosystems, cities, opinions. The models are easy to
describe and hard to keep correct, reproducible and fast. Modelly exists to remove that gap.

**What we are building**

- **A research instrument, not a toy.** Every run is seeded, every parameter lives in a typed
  scenario, every dataset lands in pandas. A result you got once is a result you can get again.
- **Fast by construction.** The hot paths of a simulation (activating agents, moving them,
  looking up neighbours, recording data) are measured, benchmarked before every release, and written so the cost
  per agent-step stays flat as models grow. Performance is a feature with a test, not a hope.
- **Small, readable modules.** A researcher should be able to open any file and understand it in
  one sitting. Files stay under 300 lines, functions under 25, and the rule is enforced by a script,
  not by goodwill. The [Pelloux guidelines](https://github.com/RemiPelloux/Modelly/blob/main/pelloux-guidelines.md) are the contract.
- **One mental model from notebook to cluster.** The same scenario object drives a quick look in a
  notebook, a browser visualization, a parameter sweep and a batch of replications.

**Where we are going.** The engine keeps one Python object per agent, which is what makes models
easy to write, and moves the heavy lifting into arrays: `Column` attributes give the model a numpy
view of every agent, continuous space answers neighbour queries for the whole population with one
KD-tree, vectorised step phases act on the whole population, and one model can be split across
processes or run its columns on a GPU ([Scale out and connect](#scale-out-and-connect)).
The [performance audit](https://github.com/RemiPelloux/Modelly/blob/main/docs/performance.md) records what has been done and what is next.

## Why Modelly

Modelly gives you the boring, load-bearing parts as small composable objects, so your model file
reads like the description of the system instead of the plumbing around it:

| Building block | What it gives you |
|---|---|
| **Scenario** | Parameters as a typed class: one run, one seed, one config object |
| **Agents** | Agent classes with a `step()`, grouped in ordered `AgentSet`s |
| **Columns** | Attributes stored in numpy arrays, readable per agent and as a whole |
| **Space** | Orthogonal / hexagonal grids, cells, networks, Voronoi meshes, continuous space |
| **Time** | Discrete ticks, events, generators and priorities in one scheduler |
| **Data** | Reporters and datasets that land in pandas, ready to plot |
| **Front end** | Browser visualization (Solara), static charts, notebooks |

No global state, no hidden step order, no bespoke loops: reproducibility is the default.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/RemiPelloux/Modelly/main/docs/images/branding/simulation-loop-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/RemiPelloux/Modelly/main/docs/images/branding/simulation-loop-light.svg">
    <img src="https://raw.githubusercontent.com/RemiPelloux/Modelly/main/docs/images/branding/simulation-loop-light.svg" alt="The Modelly loop: a scenario configures the model once; every tick the agents act, data is recorded and time advances; after the run the data is a DataFrame to visualize and analyze" width="860">
  </picture>
</p>

## Install

Modelly requires **Python 3.12+** and is published on PyPI as
[`modelly-abm`](https://pypi.org/project/modelly-abm/).

```bash
python -m venv .venv && source .venv/bin/activate
pip install modelly-abm
```

Add extras for what you need:

```bash
pip install "modelly-abm[viz]"       # + solara, matplotlib, altair
pip install "modelly-abm[network]"   # + networkx
pip install "modelly-abm[rec]"       # network + viz: what the bundled examples need
pip install "modelly-abm[geo]"       # + geopandas, rasterio, pyproj: geographic space
pip install "modelly-abm[distributed]"  # + mpi4py: split runs over MPI (dask, ray extras too)
pip install "modelly-abm[gpu]"       # + CuPy (CUDA); "modelly-abm[diff]" adds JAX, CPU everywhere
pip install "modelly-abm[calibrate]" # + optuna; xarray, mqtt and kafka extras likewise
```

To work on Modelly itself, install from a clone instead: see [Development](#development).

To depend on Modelly from your own project, add it to `pyproject.toml` (the distribution is
`modelly-abm`, the import is `modelly`):

```toml
dependencies = ["modelly-abm>=1.4"]
```

The full walkthrough, from an empty folder to a tested and replicated model, is
[docs/using_modelly_in_your_project.md](https://github.com/RemiPelloux/Modelly/blob/main/docs/using_modelly_in_your_project.md).

## A model in 30 seconds

Agents wander a grid and hand one unit of wealth to a random cellmate. Inequality emerges.
The same code ships as `example.py`.

```python
from modelly import Model
from modelly.space import CellAgent, OrthogonalMooreGrid
from modelly.scenarios import Scenario


class WealthScenario(Scenario):
    """Everything that can vary between runs lives here."""

    n: int = 120
    width: int = 12
    height: int = 12


class MoneyAgent(CellAgent):
    def __init__(self, model, cell):
        super().__init__(model)
        self.cell = cell
        self.wealth = 1

    def step(self):
        self.cell = self.cell.neighborhood.select_random_cell()
        cellmates = [a for a in self.cell.agents if a is not self]
        if self.wealth > 0 and cellmates:
            self.random.choice(cellmates).wealth += 1
            self.wealth -= 1


class WealthModel(Model):
    def __init__(self, scenario: WealthScenario = WealthScenario):
        super().__init__(scenario=scenario)
        self.grid = OrthogonalMooreGrid(
            (scenario.width, scenario.height), random=self.random
        )
        MoneyAgent.create_agents(
            self,
            scenario.n,
            self.random.choices(self.grid.all_cells.cells, k=scenario.n),
        )

    def step(self):
        self.agents.shuffle_do("step")  # every agent, in random order

    @property
    def gini(self):
        x = sorted(a.wealth for a in self.agents)
        n = len(x)
        weighted = sum(xi * (n - i) for i, xi in enumerate(x))
        return 1 + 1 / n - 2 * weighted / (n * sum(x))


model = WealthModel()
for _ in range(100):
    model.step()

print(model.gini)  # 0.0 at the start, about 0.6 after 100 ticks
```

Three pieces, and nothing else: a **scenario** of inputs, **agents** that know one thing each,
and a **model** that owns the world and advances it.

## Record it, then look at it

```python
from modelly.data.collector import DataCollector


class WealthModel(Model):
    def __init__(self, scenario: WealthScenario = WealthScenario):
        super().__init__(scenario=scenario)
        # ... grid and agents as above ...
        self.datacollector = DataCollector(
            model_reporters={"Gini": "gini"},  # anything reachable from the model
            agent_reporters={"Wealth": "wealth"},  # anything on each agent
        )

    def step(self):
        self.agents.shuffle_do("step")
        self.datacollector.collect(self)  # one row per tick
```

```python
model_vars = model.datacollector.get_model_vars_dataframe()  # Gini per tick
agent_vars = model.datacollector.get_agent_vars_dataframe()  # wealth per agent per tick
agent_vars.groupby("Step")["Wealth"].mean().plot()
```

Both frames are plain pandas, so everything you already know how to do keeps working.
Attribute reporters are gathered in C (`operator.attrgetter`), so a string reporter is the fast
path, not just the convenient one.

## Vectorise the bulk work

An agent-based model has two kinds of work: what one agent does in its `step`, which is Python
by nature, and what the model does to *all* agents at once (aggregate, filter, record, update),
which should be numpy. Declare a `Column` and the attribute lives in a model-owned array: the
agent keeps reading and writing it as before, and the model gets a zero-copy view of everyone.

```python
import numpy as np
from modelly import Agent, Column, Model


class MoneyAgent(Agent):
    wealth = Column(int, default=1)  # one numpy array for the whole class

    def step(self):
        other = self.random.choice(self.model.agents.to_list())
        if self.wealth > 0:  # per-agent access works as before
            other.wealth += 1
            self.wealth -= 1


class WealthModel(Model):
    @property
    def gini(self):
        x = np.sort(self.columns[MoneyAgent].wealth)  # view, no copy
        n = len(x)
        return 1 + 1 / n - 2 * np.sum(x * (n - np.arange(n))) / (n * x.sum())

    def tax(self):
        w = self.columns[MoneyAgent].wealth
        w[w > 10] -= 1  # bulk update, in place

    def rich(self):
        table = self.columns[MoneyAgent]
        return table.where(table.wealth > 10)  # an AgentSet
```

Nothing else changes: `model.agents`, `shuffle_do`, `DataCollector` and the examples work the
same, and attribute reporters on a column are recorded straight from the array. Measured on
10,000 agents:

| Operation | Plain attribute | Column |
|---|---|---|
| Gini coefficient | 1.09 ms | 0.03 ms |
| Count agents with `wealth > 0` | 0.94 ms | 0.008 ms |
| Mean wealth | 0.47 ms | 0.009 ms |
| Decrement every `wealth > 5` | 0.15 ms | 0.004 ms |
| `DataCollector.collect`, one reporter | 0.95 ms | 0.46 ms |
| One `agent.wealth` read inside `step` | 6 ns | 27 ns |

The last row is the trade-off: use columns for attributes you aggregate, filter, record or update
in bulk; a plain attribute is still the cheapest thing to touch inside `step`. In the Boltzmann
example the object loop is unchanged within noise while the model-level work is 30x cheaper.

### The whole population at once

Two more operations run over everyone in one call, so a model can move its population-wide phases
out of the per-agent loop:

```python
# A whole-population step for the sheep: decrement, die, reproduce, no per-agent loop.
table = self.columns[Sheep]
table.energy -= 1
table.remove_where(table.energy < 0)
table.do_where(table.draw(0.04), "spawn_offspring")  # one seeded draw per sheep

# Continuous space: one KD-tree answers the whole flock, same snapshot for all.
lists = self.space.neighbors_within(radius=5.0)
for boid in self.agents:
    boid.neighbors = lists[boid]
```

`draw` uses the model's seeded numpy generator, so the run stays reproducible. `neighbors_within`
is O(n log n) for the whole flock instead of one O(n) scan per agent, is periodic on a torus, and
is cached while no position changes. The Boids example uses it: 2,000 boids go from 98 ms to
42 ms per step.

### Replications in parallel

```python
from modelly.scenarios import RunConfiguration, run_scenarios

scenarios = WealthScenario(n=5000, rng=1).spawn_replications(32)  # 32 independent seeds
store = run_scenarios(scenarios, RunConfiguration(WealthModel, until=200), workers=8)
```

Each replication carries its own seed derived from the base scenario, so the sweep is
reproducible; `workers=` spreads it over processes.

For a plain factorial experiment, `run_grid` is the one-call version: every combination times
the replicates, each run with its own seed, results in design order whatever the number of
workers, so the DataFrame is identical to the sequential loop's.

```python
from modelly import run_grid


def season(task):  # a notebook function works: on Linux the workers are forked
    model = Orchard(budget=task["budget"], invasion=task["invasion"], rng=task["seed"])
    model.run_for(100)
    return {"harvested": model.harvested, "rotten": model.rotten}


results = run_grid(
    season, {"budget": [0, 150, 300, 600], "invasion": [3, 10, 30]}, replicates=3
)
```

### Populations as cohorts

When individuals in the same state face the same probabilities (an insect's stage, age and
sex), one row with a count replaces them all, and each per-individual draw becomes one
binomial draw per row with exactly the same law. `CohortTable` holds such a population with no
agent objects; the stage-structured playbook runs 243x faster than its individual Mesa 2.3
version and agrees with it statistically.

```python
from modelly import CohortTable

insects = CohortTable(model.rng, stage=np.int8, age=np.int16, female=bool)
insects.add(500, stage=EGG)
insects.thin(daily_survival[insects["stage"]])  # Binomial(count, s) per row
insects.split(0.5, where=emerging, stage=ADULT, female=True)  # sex at emergence
eggs = insects.draw(lay_prob, where=mature_females).sum() * clutch
```

## Scale out and connect

Each item keeps the authoring model above; each number is measured on one laptop and recorded
in the docs it links to, shortfalls included.

- **Split runs** (`modelly.distributed`): one model across processes with MPI, Dask or locally,
  byte-identical to a single process at 1, 2, 4 and 16 partitions; weak scaling on a 16-core
  laptop stays far below a cluster's, 62% at 2 workers and 9% at 16 ([guide](https://github.com/RemiPelloux/Modelly/blob/main/docs/distributed.md)).
- **GPU backend** (`modelly.gpu`): columns, cohorts and cell operations on CuPy or JAX, same
  integer state as numpy; 34x faster at 10 million agents on a laptop RTX 5050, slower at
  20,000 ([guide](https://github.com/RemiPelloux/Modelly/blob/main/docs/gpu.md)).
- **Differentiable models** (`modelly.diff`): JAX-traced phases and gradient calibration that
  recovers known parameters on two zoo models ([guide](https://github.com/RemiPelloux/Modelly/blob/main/docs/differentiable.md)).
- **Live data and assimilation** (`modelly.stream`): sources, replicate ensembles, a particle
  filter (nowcast error 5 people against 69 unfiltered on the tutorial's synthetic truth) and an
  ensemble Kalman filter ([tutorial](https://github.com/RemiPelloux/Modelly/blob/main/docs/assimilation.md)).
- **Fields and ODEs** (`modelly.couple`): diffusion, advection and decay on a grid layer, ODE and
  stock-flow parts, a checked coupling schedule; mass conserved to round-off ([guide](https://github.com/RemiPelloux/Modelly/blob/main/docs/coupling.md)).
- **Emulators and history matching** (`modelly.emulate`): Gaussian-process and neural emulators,
  active learning, waves that shrink the plausible space from 17% to 2.5% on the SEIR zoo model ([guide](https://github.com/RemiPelloux/Modelly/blob/main/docs/emulators.md)).
- **Synthetic populations** (`modelly.population`): people from census tables, households,
  places and contact networks; three zoo models on real Burlington data, licences bundled ([guide](https://github.com/RemiPelloux/Modelly/blob/main/docs/population.md)).
- **A model in the browser**: `modelly export-web model.py:Model` writes a static site that runs
  it in Pyodide; every bundled model verified in headless Chromium; first load 8 s on a 50 Mbit/s
  line for a model without scipy, 21 s on a fast 4G profile ([guide](https://github.com/RemiPelloux/Modelly/blob/main/docs/browser.md)).
- **Studio II**: ensemble, assimilation, experiment, analysis and WebGL map tabs, a session
  recorded as a script that reproduces the run ([guide](https://github.com/RemiPelloux/Modelly/blob/main/docs/studio.md)).
- **Tools**: a NetLogo translator for a stated subset ([guide](https://github.com/RemiPelloux/Modelly/blob/main/docs/netlogo.md)),
  `modelly lint --lsp` for editors, pre-commit hooks, 21 lint rules, strict typing on the
  research packages.

## Modelly, Mesa, NetLogo or Agents.jl?

| | Modelly | Mesa | NetLogo | Agents.jl |
|---|---|---|---|---|
| Language | Python | Python | NetLogo | Julia |
| Authoring model | `Model`, `Agent`, `AgentSet`, typed `Scenario` | `Model`, `Agent`, `AgentSet` | turtles, patches, links | `ABM`, agent structs |
| Per-agent attributes in arrays | `Column`: one numpy array per attribute, zero-copy views | no | no | yes |
| Population-wide operations | `draw`, `do_where`, `remove_where`, one KD-tree query per step | per-agent loops | built-in primitives | vectorised |
| Time | ticks, scheduled events, generators, priorities, hybrid ABM/DES | ticks, events | ticks | ticks, events |
| Reproducibility | one seed on the scenario, derived seeds per replication | model seed | run seed | model RNG |
| Data out | pandas, incremental frames | pandas | CSV, BehaviorSpace | DataFrames.jl |
| Visualization | Solara in the browser, matplotlib, altair | Solara | built-in GUI | Makie |
| Moving from Mesa | codemod plus a construct-by-construct guide | – | – | – |

Pick Modelly when you want Mesa's authoring model with numpy underneath, measured performance,
and a scenario object that makes every run reproducible. Pick NetLogo for teaching and its GUI,
Agents.jl when the rest of your stack is Julia.

## Coming from Mesa

Modelly's authoring model is the one Mesa 3 users know (`Model`, `Agent`, `AgentSet`,
`DataCollector`), with one grid system and no schedulers. A codemod does the mechanical part of a
move and reports the rest, each line pointing at a section of the guide:

```bash
python -m modelly.migrate path/to/your/model/          # dry run: diff plus report
python -m modelly.migrate path/to/your/model/ --write  # apply the rewrites
```

It rewrites imports to the domain-package paths (`modelly.space`, `modelly.time`, `modelly.data`,
`modelly.batch`, `modelly.viz`), agent constructors and scheduler attributes, and flags scheduler classes,
legacy grid calls, `batch_run`, simulators and `seed=` for you to decide. The construct-by-construct
map, for Mesa 2.x and 3.x, is [docs/migrating_from_mesa.md](https://github.com/RemiPelloux/Modelly/blob/main/docs/migrating_from_mesa.md).

## Checking a model

A static check finds the bugs that break reproducibility (random draws outside the model's
generators, wall-clock values, a missing `super().__init__`, loops over sets) and the loops that
make a step O(N²) (an agent scanning `self.model.agents`, nested population loops):

```bash
python -m modelly.lint path/to/your/model/   # exits 1 on findings, so it works in CI
python -m modelly.lint --explain MDL101      # why a rule matters, with a fix
python -m modelly.lint --diff src/           # the safe fixes (MDL001, 002, 003, 009) as a diff
python -m modelly.lint --fix src/            # apply them, then report what is left
```

A new project starts clean: `modelly new my-model --template grid` (or `network`, `continuous`,
`cohort`, `geo`, `llm`) writes a package with a seeded scenario, an agent and a model, a determinism test, the
lint settings and a README with an ODD outline. See
[docs/new_project.md](https://github.com/RemiPelloux/Modelly/blob/main/docs/new_project.md).
In Jupyter, `%load_ext modelly.ipython` adds `%modelly lint` and `%modelly profile`, and a model
displays its scenario, time and population by agent class.

Every tool is also one command: `python -m modelly --help` (or `modelly --help` once installed)
lists them, and `modelly lint src/` is `python -m modelly.lint src/`. Every rule, with the fix, is in [docs/lint.md](https://github.com/RemiPelloux/Modelly/blob/main/docs/lint.md);
`modelly lint --lsp` serves the same findings and fixes to an editor over the language server
protocol, and `.pre-commit-hooks.yaml` offers `modelly-lint` and `modelly-lint-fix` to pre-commit.

Its runtime companion runs the model and shows where each step's time goes: every
`AgentSet.do` / `shuffle_do` call by agent class and method, with its cost per agent,
`DataCollector.collect`, scheduled events, births and deaths, plus hints that point at lint codes:

```bash
python -m modelly.profile path/to/model.py:MyModel --steps 100 --param n=5000
```

From Python, `with modelly.profile.Profiler(model) as prof: model.run_for(100)`, then
`prof.report()` or `prof.to_dataframe()`. See [docs/profile.md](https://github.com/RemiPelloux/Modelly/blob/main/docs/profile.md).

## Checkpoints

A long run can be saved and resumed bit for bit, in the same process or a new one:

```python
model.run_for(50)
model.save("run.ckpt")  # agents, spaces, events, data, both generators
model = WolfSheep.load("run.ckpt")  # only load files you trust: it is a pickle
model.run_for(50)  # identical to running 100 steps in one go
model.checkpoint_every(100, "run-{time:05.0f}.ckpt")
```

See [docs/checkpoints.md](https://github.com/RemiPelloux/Modelly/blob/main/docs/checkpoints.md).

## Architecture

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/RemiPelloux/Modelly/main/docs/images/branding/architecture-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/RemiPelloux/Modelly/main/docs/images/branding/architecture-light.svg">
    <img src="https://raw.githubusercontent.com/RemiPelloux/Modelly/main/docs/images/branding/architecture-light.svg" alt="Modelly architecture" width="860">
  </picture>
</p>

- **Scenario to Model.** Inputs enter through one typed object; the model owns state, seed, RNG and
time.
- **Model to AgentSet / Space / Time.** Agents live in sets, act inside some space, and are driven
by the scheduler.
- **Model to Dataset.** Reporters sample the model and its agents on intervals you choose.
- **Dataset to Visualize / Analyze / Reproduce.** Same data, three exits: a browser app, a
dataframe, or a seeded re-run.

## Package layout

One package per domain; each `__init__.py` lists its public names in `__all__`.

| Package | What it holds |
|---|---|
| `modelly.core` | `Agent`, `Model`, `AgentSet`, `Column`, `FastRandom`, exceptions |
| `modelly.space` | cells, orthogonal and hex grids, networks, Voronoi, property layers, continuous space (`modelly.space.continuous`) |
| `modelly.time` | `Schedule`, events, event generators, priorities, signals (`modelly.time.signals`) |
| `modelly.data` | `DataCollector`, reporters, dataset recorders (`modelly.data.recorders`) |
| `modelly.behaviour` | timed actions (`actions`), continuous states and thresholds (`states`), meta-agents (`meta_agents`) |
| `modelly.scenarios` | `Scenario`, `RunConfiguration`, `run_scenarios`, result stores |
| `modelly.batch` | `run_batch`, `run_grid`, `CohortTable` |
| `modelly.viz` | Solara app, space renderer, matplotlib and altair backends, command console |
| `modelly.experiments` | `ScenarioSpace`, designs, executors (processes, threads, Dask, Ray, SLURM, PBS), a Parquet and DuckDB results store |
| `modelly.calibrate` | ABC rejection and SMC, simulated moments, Bayesian optimisation, posteriors |
| `modelly.sensitivity` | OAT, Morris, Sobol, PAWN, emulators as stand-ins |
| `modelly.emulate` | Gaussian-process and neural emulators, active learning, history matching |
| `modelly.distributed` | split runs: partitioners, halo exchange, MPI, Dask and Ray backends, `check_independence` |
| `modelly.gpu` | columns, cohorts and cell operations on CuPy or JAX, Philox streams |
| `modelly.diff` | JAX-traced phases, gradient checks, `GradientCalibration` |
| `modelly.stream` | live sources, `Ensemble`, `ParticleFilter`, `EnsembleKalmanFilter` |
| `modelly.couple` | `Field`, `ODE`, `StockFlow`, the coupling schedule |
| `modelly.population` | synthetic populations, households, places, contact networks |
| `modelly.provenance` | `modelly run`, `verify`, `bundle`, `odd`: manifests and archivable studies |
| `modelly.timetravel` | checkpoint rings, rewind, replay, branch, run diff |
| `modelly.llm` | language-model agents with a replayable response cache |
| `modelly.studio` | `modelly studio`, the browser workbench |
| `modelly.web` | `modelly export-web`, a model as a static site |
| `modelly.zoo` | 17 validated models, each with a test against a known result |
| `modelly.netlogo` | `modelly netlogo`, the NetLogo translator |
| `modelly.lint` | `python -m modelly.lint`, static checks for models, `--lsp` |
| `modelly.profile` | `python -m modelly.profile` and `Profiler`, where a running model's time goes |
| `modelly.migrate` | `python -m modelly.migrate`, the Mesa codemod |
| `modelly._native` | the five compiled modules (`fastrng`, `fastloop`, `fastcell`, `fastset`, `fastevents`), each with a pure-Python twin |

The top-level names (`modelly.Agent`, `modelly.Model`, `modelly.DataCollector`, `modelly.Column`,
`modelly.CohortTable`, `modelly.FastRandom`, `modelly.run_batch`, `modelly.run_grid`) import from
`modelly` directly.

## How the engine stays fast

The data structures are chosen for the operations a simulation actually performs, and each choice
is backed by a measurement in [docs/performance.md](https://github.com/RemiPelloux/Modelly/blob/main/docs/performance.md).

| Structure | Backed by | Why |
|---|---|---|
| `AgentSet` (every view) | ordered `dict` keyed on `weakref.ref` | O(1) membership and removal, stable order for reproducible shuffles, no zombie agents; half the cost of `WeakKeyDictionary` |
| `model.agents` (the registry) | ordered `dict` keyed on the agent | Strong references where the lifecycle is explicit; views downgrade to weak sets in one place |
| `Cell.agents` | `list` | Cells hold a handful of agents; append and remove beat any indexed structure at that size |
| Cell neighbourhoods | per-cell `dict` cache | One lookup per query; invalidating one cell never touches another, and a discarded grid is freed |
| Empty cells in any discrete space | swap-remove list + index | O(1) random empty cell at any fill level, built lazily the first time a space turns out to be dense |
| Property layers | `np.ndarray` per layer | Vectorised updates on the array, per-cell accessors on the cells, one source of truth |
| Continuous space | one `np.ndarray` of positions, one KD-tree per step | Per-agent queries are numpy; `neighbors_within` answers the whole population in one periodic tree query |
| Event queue | a compiled binary heap (`fastevents.c`) with lazy cancellation and compaction | O(log n) scheduling that never degrades under repeated cancel/reschedule; the same ordering as its pure-Python twin |

## Benchmarks

Two questions, two methods, both in the repository.

**Same code on both frameworks.** A research notebook written for Mesa 2.3, ported with the
codemod and nothing else changed, identical seeds, outputs checked bit-identical, CPU time
pinned and alternating: Modelly runs at Mesa's speed within a few percent (0.94 of Mesa's time
seeded with `FastRandom`, 1.02 to 1.04 with `random.Random`); that model spends most of its
time in its own code. Two public playbooks ported the same way (`benchmarks/ports/`), which
spend most of theirs in framework calls, run at 0.22 and 0.37 of Mesa 2.3's time with
bit-identical output. Five playbooks ported from their Mesa 3.5 versions by the codemod alone
(`benchmarks/ports_mesa3/`) run at 0.45 to 0.93 of Mesa 3.5's time; they are not bit-identical
(the random streams differ) but agree in distribution over 100 seeds. The method and every
round are in
[docs/performance.md](https://github.com/RemiPelloux/Modelly/blob/main/docs/performance.md).

**Same model, each framework's own idiom.** `benchmarks/playbooks/` holds eight models written
for Mesa 2.3 and for the current Mesa 3.5 the way their APIs intend, four of them also for the
vectorised mesa-frames, three also as a hand-vectorised Mesa 3.5 baseline, and for Modelly with columns, vectorised phases, `CellIndex` and one
KD-tree per step. The runner executes each in its own environment, pinned to one core, rotating
the order every round, checks that the implementations agree in distribution (over shared
seeds, every statistic) and that each is deterministic, and records the machine and versions.
CPU seconds of the steps at the large size, median of ten rounds in one session on a
performance core, this machine, at a fixed 1.9 GHz base frequency (performance governor, turbo
disabled; every per-round ratio within 15% of its median). Absolute seconds are therefore longer
than with turbo; the ratios are the point:

| Playbook | Mesa 2.3 | Mesa 3.5 | Mesa 3.5 + numpy | mesa-frames | Modelly, cell lists | Modelly | vs Mesa 2.3 | vs Mesa 3.5 | vs mesa-frames |
|---|---|---|---|---|---|---|---|---|---|
| Grid epidemic (SIR, random walk, synchronous) | 7.10 s | 4.31 s | 0.035 s | 1.10 s | 2.87 s | 0.157 s | 45x | 27x | 7.0x |
| Predator-prey with grass (births and deaths every step) | 3.39 s | 3.73 s |  |  | 2.19 s | 0.526 s | 6.4x | 7.1x |  |
| Flocking in continuous space | 24.58 s | 24.66 s |  |  |  | 0.749 s | 33x | 33x |  |
| Virus on a random network | 7.81 s | 2.51 s |  |  |  | 0.199 s | 39x | 13x |  |
| Stage-structured insect population, individuals | 3.67 s | 2.01 s |  |  |  | 0.684 s | 5.4x | 2.9x |  |
| Same population as a `CohortTable` (binomial thinning) | 3.67 s | 2.01 s |  |  |  | 0.015 s | 243x | 133x |  |
| Schelling segregation (moves to random empty cells) | 4.65 s | 3.58 s | 0.116 s | 1.93 s | 0.32 s | 0.205 s | 23x | 18x | 9.4x |
| Boltzmann wealth exchange, Gini by a `DataCollector` | 2.14 s | 1.14 s | 0.121 s | 1.00 s |  | 0.335 s | 6.4x | 3.4x | 3.0x |
| Sugarscape, constant growback (vision, best sugar in sight) | 1.49 s | 1.46 s |  | 2.10 s | 1.13 s | 0.325 s | 4.6x | 4.5x | 6.5x |

"Mesa 3.5 + numpy" (`mesa3np_model.py`) is what a Mesa modeller can write by giving up agent
objects: a `mesa.Model` holding the population as numpy arrays over Mesa's grid and property
layers, with the same vectorised phases as Modelly. It is faster than Modelly's columns (4.4x on
the epidemic, 1.8x on Schelling, 2.8x on Boltzmann): Modelly keeps an `Agent` per individual,
with its `step()`, its identity and the agent-set API, and pays for that bookkeeping. With agents
on both sides, Modelly columns are 2.9 to 33x faster than Mesa 3.5, 4.6 to 45x faster than
Mesa 2.3 (4.0 to 32x including construction) and 3.0 to 9.4x faster than mesa-frames.

Where Modelly keeps Mesa's data structure (agents held in cell lists, `modelly-cells` in the
results) the gap closes to 1.3 to 2.5x over Mesa 2.3 on the epidemic, predator-prey and
Sugarscape models: the layout is where the time is, not the interpreter. (Schelling's model with
cell lists stays 14x ahead of Mesa 2.3: it counts every resident's similar neighbours at once.)
Every vectorised phase rests on a stated equivalence argument, in
[docs/vectorised_phases.md](https://github.com/RemiPelloux/Modelly/blob/main/docs/vectorised_phases.md); the full tables with the agreement
checks are in [benchmarks/playbooks/results/README.md](https://github.com/RemiPelloux/Modelly/blob/main/benchmarks/playbooks/results/README.md).

## Future roadmap

Each release page records what shipped and what fell short, measured: [1.3.0](https://github.com/RemiPelloux/Modelly/blob/main/docs/roadmap/1.3.0.md)
(calibration, sensitivity, experiments, provenance, Studio, the zoo) and [1.4.0](https://github.com/RemiPelloux/Modelly/blob/main/docs/roadmap/1.4.0.md)
(the section above). Next, in order and without dates: [1.5.0](https://github.com/RemiPelloux/Modelly/blob/main/docs/roadmap/1.5.0.md),
a model hub with model cards, policy and causal tools, more language-model agents, R and Julia
bindings; then [2.0.0](https://github.com/RemiPelloux/Modelly/blob/main/docs/roadmap/2.0.0.md), one space API, one clock, columns by
default, typed scenarios, a stable ABI and checkpoint format, with its deprecations already
announced in [docs/deprecations.md](https://github.com/RemiPelloux/Modelly/blob/main/docs/deprecations.md). Each item keeps today's authoring
model: you still write a `Model`, an `Agent` subclass and a `Scenario`.

## Built-in examples

Real, runnable models that ship with the package, good reading material for the patterns above.

| Model | Shows | Path |
|---|---|---|
| Boltzmann Wealth | Money exchange on a grid, emerging inequality | `modelly/examples/basic/boltzmann_wealth_model` |
| Schelling | Segregation from local tolerance thresholds | `modelly/examples/basic/schelling` |
| Conway's Game of Life | Cellular automaton, cell-state transitions | `modelly/examples/basic/conways_game_of_life` |
| Virus on Network | SIR epidemic on a contact network | `modelly/examples/basic/virus_on_network` |
| Boid Flockers | Continuous space, alignment and cohesion | `modelly/examples/basic/boid_flockers` |
| Wolf Sheep | Predator and prey ecology on a grid | `modelly/examples/advanced/wolf_sheep` |
| Sugarscape G1MT | Resource harvesting, trade and growth | `modelly/examples/advanced/sugarscape_g1mt` |
| Epstein Civil Violence | Regime shifts from agent state | `modelly/examples/advanced/epstein_civil_violence` |
| Prisoner's Dilemma | Pairwise strategic interaction | `modelly/examples/advanced/pd_grid` |
| Alliance Formation | Network structure and group formation | `modelly/examples/advanced/alliance_formation` |

The zoo adds 17 research models with validation tests (age-structured SEIR, Bass diffusion,
Schelling on real census tracts, traffic on OpenStreetMap streets, a hospital-capacity
epidemic): `python -m modelly.zoo list`, documented in [docs/zoo](https://github.com/RemiPelloux/Modelly/blob/main/docs/zoo/index.md).

Run one:

```bash
solara run modelly/examples/basic/boltzmann_wealth_model/app.py   # browser UI
modelly export-web modelly.zoo.forest_fire.model:ForestFire --out site/   # the same, as a static site
```

## Documentation

| Where | What |
|---|---|
| **Documentation site** | [remipelloux.github.io/Modelly](https://remipelloux.github.io/Modelly/): everything below, rendered and searchable |
| **Use it in your project** | `docs/using_modelly_in_your_project.md`: install, layout, model, data, replications |
| **Migrating from Mesa** | `docs/migrating_from_mesa.md`: construct-by-construct map, plus `python -m modelly.migrate` |
| **Tutorials** | `docs/tutorials/`: 12 notebooks, from *your first model* to *hybrid ABM/DES* |
| **Overview** | `docs/overview.md`: the object model, end to end |
| **Performance audit** | `docs/performance.md`: measurements, what changed, what is next |
| **Best practices** | `docs/best-practices.md` |
| **Starting a project** | `docs/new_project.md`: `modelly new` and its templates |
| **Checking a model** | `docs/lint.md`: the `python -m modelly.lint` rules, `--fix` and `--diff` |
| **Profiling a model** | `docs/profile.md`: `python -m modelly.profile`, the report and its hints |
| **Checkpoints** | `docs/checkpoints.md`: save a run, resume it bit for bit |
| **A study, end to end** | `docs/experiments.md`, `docs/calibration.md`, `docs/sensitivity.md`, `docs/provenance.md`, `docs/timetravel.md`, `docs/llm_agents.md` |
| **Scale out and connect** | `docs/distributed.md`, `docs/gpu.md`, `docs/differentiable.md`, `docs/assimilation.md`, `docs/coupling.md`, `docs/emulators.md`, `docs/population.md`, `docs/browser.md`, `docs/studio.md`, `docs/netlogo.md`, `docs/r_and_julia.md` |
| **API reference** | `docs/apis/`: agents, agent sets, columns, model, space, time, data, migrate |
| **Changelog** | `CHANGELOG.md`: what each release added, changed and fixed |

The tutorials are executable: open them locally, in Colab, or through Binder (links at the top of
each notebook).

## Development

```bash
git clone https://github.com/RemiPelloux/Modelly.git && cd Modelly
pip install -e ".[dev]"
bash scripts/ci-local.sh          # lint, format, strict types, tests, size audit: the local gate
bash scripts/release-checks.sh    # before a release: MPI, SLURM, bundles, Pyodide, browsers, docs, bench
bash scripts/ci-local.sh --list   # stage names, run a subset with: ci-local.sh lint test
python -m modelly.dev gate        # the same gate without bash: Windows, macOS and Linux
bash scripts/build-native.sh      # compile modelly/_native in place; MODELLY_PURE_PYTHON=1 forces the Python twins
```

The coverage badge at the top of this page is produced by that gate: the test stage measures
coverage and rewrites `docs/images/badges/coverage.svg`, so commit the badge with your change.
Hosted CI runs only two workflows: the Release workflow builds the wheels for Linux, macOS and
Windows on a tag and publishes to PyPI, and the docs workflow publishes the site; every other
check runs on the maintainer's machine before a release, on Linux x86-64.

Code discipline is written down in [pelloux-guidelines.md](https://github.com/RemiPelloux/Modelly/blob/main/pelloux-guidelines.md): small files,
short functions, surgical changes, conventional commits. `scripts/audit-pelloux.sh` enforces the
size limits against `pelloux-baseline.json`; legacy oversized files are listed there and may shrink
but never grow. The repository layout and how the brand assets are generated are in
[CONTRIBUTING.md](https://github.com/RemiPelloux/Modelly/blob/main/CONTRIBUTING.md).

## Contributing

Issues, ideas and pull requests are welcome on the
[issue tracker](https://github.com/RemiPelloux/Modelly/issues). If you are adding a feature, opening
a ticket first is the fastest route: it keeps the patch small and reviewable.

Everything you need is in [CONTRIBUTING.md](https://github.com/RemiPelloux/Modelly/blob/main/CONTRIBUTING.md): local setup, tests, the lint and
format commands the gate runs, docs, and how a pull request is reviewed. By taking part you agree to
our [Code of Conduct](https://github.com/RemiPelloux/Modelly/blob/main/CODE_OF_CONDUCT.md).

## Citing

If Modelly contributes to a publication, cite it with the metadata in [CITATION.cff](https://github.com/RemiPelloux/Modelly/blob/main/CITATION.cff)
(GitHub shows a "Cite this repository" button that formats it for you). The paper in
[paper/](https://github.com/RemiPelloux/Modelly/tree/main/paper) describes release 1.4.0, with every number traced to a file in this repository.

## License

Modelly is released under the [Apache License 2.0](https://github.com/RemiPelloux/Modelly/blob/main/LICENSE). Third-party attribution is recorded in
[NOTICE](https://github.com/RemiPelloux/Modelly/blob/main/NOTICE).

<p align="center"><sub>Modelly: build the system, run the world, watch what emerges.</sub></p>
