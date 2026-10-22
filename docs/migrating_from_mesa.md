# Migrating from Mesa

Modelly's authoring model will feel familiar if you have written a Mesa model: a `Model`
subclass owns the world, `Agent` subclasses hold behaviour, a `DataCollector` records. The
differences are where Mesa accumulated several generations of API (schedulers, two grid systems,
`batch_run`) and Modelly keeps one. This page maps every Mesa construct to its Modelly
equivalent, for Mesa 2.x and Mesa 3.x code alike.

Start with the codemod. It rewrites the mechanical parts (imports, agent constructors, a few
model attributes) and prints a report of every line that needs a decision, each pointing to a
section below:

```bash
python -m modelly.migrate path/to/your/model/          # dry run: shows the diff and the report
python -m modelly.migrate path/to/your/model/ --write  # applies the rewrites
```

Then work through the report top to bottom. A typical Mesa 3 model is done after the imports;
a Mesa 2 model needs the scheduler and grid sections.

## Imports

| Mesa | Modelly |
|---|---|
| `import mesa` | `import modelly` |
| `from mesa import Agent, Model, DataCollector` | `from modelly import Agent, Model, DataCollector` |
| `mesa.datacollection` | `modelly.datacollection` |
| `mesa.discrete_space` (3.2+), `mesa.experimental.cell_space` (3.0, 3.1) | `modelly.discrete_space` |
| `mesa.space` (`MultiGrid`, `SingleGrid`, `NetworkGrid`, `ContinuousSpace`) | `modelly.discrete_space`, see [Grids](#grids-and-positions) |
| `mesa.time` (schedulers) | nothing to import, see [Activation](#activation-and-schedulers) |
| `mesa.batchrunner.batch_run` | `modelly.experimental.scenarios`, see [Batch runs](#batch-runs) |
| `mesa.visualization` | `modelly.visualization` (same component names) |
| `mesa.experimental.devs` (`ABMSimulator`, `DEVSimulator`) | methods on `Model`, see [Events](#events-and-simulators) |
| `mesa.experimental.continuous_space` | `modelly.experimental.continuous_space` |
| `mesa.experimental.signals`, `mesa.experimental.meta_agents` | `modelly.experimental.signals`, `modelly.experimental.meta_agents` |

The codemod does all of these.

## Agents

**Constructor.** Mesa 2 agents took an id; Modelly assigns `unique_id` itself, starting at 1:

```python
# Mesa 2
class Sheep(mesa.Agent):
    def __init__(self, unique_id, model, energy):
        super().__init__(unique_id, model)


# Modelly (and Mesa 3)
class Sheep(Agent):
    def __init__(self, model, energy):
        super().__init__(model)
```

`model.next_id()` no longer exists; delete those calls. The codemod rewrites the `super()` call
and flags the constructor signature so you remove the parameter from the callers too.

**Random numbers.** `self.random` and `self.model.random` work as in Mesa, and `self.rng` is a
seeded numpy `Generator`. Never use the `random` module or `np.random` directly.

**Creating many agents.** `Sheep.create_agents(model, n, energy=energies)` creates `n` agents in
one call; a sequence of length `n` gives one value per agent, anything else is broadcast.

## Activation and schedulers

Mesa 2 schedulers are gone (Mesa 3 removed them as well). Activation is a method call on an
`AgentSet`, and `model.agents` is always up to date, so there is no `schedule.add`:

| Mesa 2 | Modelly |
|---|---|
| `self.schedule = RandomActivation(self)` | delete |
| `self.schedule.add(agent)` | delete; agents register themselves |
| `self.schedule.step()` | `self.agents.shuffle_do("step")` |
| `BaseScheduler` (insertion order) | `self.agents.do("step")` |
| `SimultaneousActivation` | `self.agents.do("step"); self.agents.do("advance")` |
| `StagedActivation(stage_list=["a", "b"])` | `self.agents.do("a"); self.agents.do("b")` |
| `RandomActivationByType` | `self.agents_by_type[Sheep].shuffle_do("step")`, one line per type |
| `self.schedule.steps` | `self.time` |
| `self.schedule.get_agent_count()` | `len(self.agents)` |
| `self.schedule.agents` | `self.agents` |
| `self.schedule.remove(agent)` | `agent.remove()` |

Mesa 3's `self.agents.shuffle_do("step")`, `select`, `groupby`, `agg`, `get` and `set` exist with
the same signatures.

## Grids and positions

Modelly has one grid system, the cell space (`modelly.discrete_space`), which Mesa 3 ships as
`mesa.discrete_space`. Mesa 2's `mesa.space.MultiGrid` and `SingleGrid` translate as follows. An
agent that lives on a grid subclasses `CellAgent` and has a `cell` instead of a `pos`.

| Mesa 2 (`mesa.space`) | Modelly |
|---|---|
| `MultiGrid(width, height, torus)` | `OrthogonalMooreGrid((width, height), torus=torus, random=self.random)` |
| `SingleGrid(width, height, torus)` | same, with `capacity=1` |
| Von Neumann neighbourhoods (`moore=False`) | `OrthogonalVonNeumannGrid(...)` |
| `HexGrid` | `HexGrid((width, height), ...)` |
| `NetworkGrid(G)` | `Network(G, random=self.random)` |
| `grid.place_agent(agent, pos)` | `agent.cell = grid[pos]` |
| `grid.move_agent(agent, pos)` | `agent.cell = grid[pos]` |
| `grid.move_to_empty(agent)` | `agent.cell = grid.select_random_empty_cell()` |
| `grid.remove_agent(agent)` | `agent.cell = None` (or `agent.remove()` to leave the model) |
| `agent.pos` | `agent.cell.coordinate` |
| `grid.get_neighbors(pos, moore=True, include_center=False, radius=1)` | `agent.cell.neighborhood.agents` (radius 1) or `agent.cell.get_neighborhood(radius=r, include_center=...).agents` |
| `grid.get_neighborhood(pos, ...)` | `agent.cell.get_neighborhood(radius=r)` (cells) |
| `grid.get_cell_list_contents([pos])` | `grid[pos].agents` |
| `grid.is_cell_empty(pos)` | `grid[pos].is_empty` |
| `grid.empties` | `grid.empties` |
| `grid.coord_iter()` | `for cell in grid.all_cells: cell.coordinate, cell.agents` |
| `grid.out_of_bounds(pos)` | not needed: `grid[pos]` raises for a missing cell |
| `grid.width`, `grid.height` | same |
| `PropertyLayer` | `grid.create_property_layer("sugar", default_value=0.0)`; then `cell.sugar` and `grid.sugar` |

Moving along the grid: `agent.move_relative((dx, dy))`, or `Grid2DMovingAgent` with
`agent.move("north")`.

`ContinuousSpace` lives under `modelly.experimental.continuous_space`; agents subclass
`ContinuousSpaceAgent`, keep their position in a shared numpy array, and query with
`get_neighbors_in_radius` and `get_nearest_neighbors`.

## Model

| Mesa | Modelly |
|---|---|
| `Model(seed=42)` | `Model(rng=42)`, or a `Scenario(rng=42)` passed as `scenario=` |
| `self.running` | same |
| `model.step()`, `model.run_model()` | same; `run_for(duration)` and `run_until(t)` added |
| `self.steps` (Mesa 3) | `self.time` |
| `self.agents`, `self.agents_by_type` (Mesa 3) | same |

Parameters belong in a `Scenario` subclass (typed defaults plus the seed) rather than in the
model's `__init__` signature; see [Using Modelly in your project](using_modelly_in_your_project.md).

## Data collection

`DataCollector` keeps Mesa's API: `model_reporters`, `agent_reporters`, `agenttype_reporters`,
`tables`, `collect(model)`, `get_model_vars_dataframe()`, `get_agent_vars_dataframe()`,
`get_agenttype_vars_dataframe(type)`, `get_table_dataframe(name)`. Attribute-name reporters
(`{"energy": "energy"}`) are the fast path. Declaring an attribute as a `Column` makes
`model.columns[Sheep].energy` a numpy view, which is the Modelly way to write a vectorised
model reporter.

## Batch runs

Mesa's `batch_run(Model, parameters, iterations, max_steps, ...)` becomes scenarios and a runner:

```python
from concurrent.futures import ProcessPoolExecutor

from modelly.experimental.scenarios import RunConfiguration, run_scenarios

scenarios = [
    s
    for density in (0.6, 0.7, 0.8)
    for s in MyScenario(density=density, rng=1).spawn_replications(10)
]
config = RunConfiguration(MyModel, until=100)

with ProcessPoolExecutor() as pool:
    store = run_scenarios(scenarios, config, executor=pool)
```

Each replication has its own seed derived from the base scenario, so the sweep is reproducible.
For a quick loop, `for scenario in base.spawn_replications(n): model = MyModel(scenario)`.

## Events and simulators

`ABMSimulator`, `DEVSimulator` and `mesa.experimental.devs` do not exist. The model schedules
directly: `self.schedule_event(fn, at=t)` or `after=dt`, `self.schedule_recurring(fn, Schedule(interval=2.0))`,
and `run_for` / `run_until` advance time through the same event list that drives `step`.

## Visualization

`SolaraViz`, `SpaceRenderer`, `make_space_component`, `make_plot_component`, `Slider` and the
portrayal style classes keep their Mesa 3 names and signatures under `modelly.visualization`.
Mesa 2's `ModularServer` and the JavaScript modules have no equivalent; rewrite those
visualisations with `SolaraViz` (tutorial 6).

## Checklist

1. Run the codemod, read the report.
2. Replace schedulers with `AgentSet` calls; delete `schedule.add`.
3. Move grid code to cells: `agent.cell`, `cell.neighborhood`, `grid.select_random_empty_cell()`.
4. Move parameters into a `Scenario`; pass `rng` instead of `seed`.
5. Run your tests with `-W error`; Modelly raises instead of warning for removed APIs.
