# Changelog

All notable changes to Modelly. The format follows Keep a Changelog; versions follow semantic
versioning.

## 1.3.0 - 2026-10-22

### Added

- Published on PyPI as `modelly-abm` (`pip install modelly-abm`); the import name stays `modelly`.
- Vectorised step phases on column tables: `table.draw(p)` gives one seeded Bernoulli draw per
  agent (scalar or per-row probabilities), `table.do_where(mask, "method")` calls a method on
  the masked agents, alongside `remove_where`. A whole-population step reads
  `energy -= 1; remove_where(energy < 0); do_where(draw(p), "spawn")`.
- Parallel replications: `run_scenarios(..., workers=n)` runs the scenarios in a process pool
  it creates and closes itself.
- The O(1) empty-cell index now serves every discrete space (networks, Voronoi meshes), not
  only grids: `select_random_empty_cell` builds it lazily and `cell.empty` keeps it current.
- Smart caches: `DataCollector.get_agent_vars_dataframe` converts only the steps collected
  since the previous call and appends them; `ContinuousSpace.neighbors_within` reuses its
  lists while no position changed (keyed on the positions' content).
- The architecture diagram animates one synchronised tick: a token leaves the scenario,
  crosses the model, the recorder and the dataset, fans out to the exits and loops back,
  each card glowing as it arrives.

### Changed

- `ColumnStore` and `ColumnTable` take the model's numpy generator; `table.rng` is available.
- `Grid` no longer owns an empties index; the base `DiscreteSpace` does, and the error for a
  full space names the space class.

## 1.2.0 - 2026-10-22

### Added

- `ContinuousSpace.neighbors_within(radius)`: one KD-tree query for the whole population
  (periodic on a torus), O(n log n) instead of one O(n) scan per agent. The Boids example uses
  it for a simultaneous update: 2,000 boids go from 98 ms to 42 ms per step, 10,000 boids run
  at 227 ms per step.
- `CellCollection.empties`: the empty cells of a neighbourhood or a space without a property
  call per cell; `DiscreteSpace.empties` and the Epstein example use it.
- `ColumnTable.remove_where(mask)`: the whole-population "die" phase in one call.
- `py.typed`, so type checkers use Modelly's annotations.

### Changed

- Iterating `model.agents` walks a snapshot, like every other `AgentSet`: removing agents
  inside the loop no longer raises.
- `ContinuousSpace.get_agents_in_radius` resolves hits by index instead of a Python pass over
  the whole population.
- The Boids example determines neighbours from the positions at the start of the step (all
  boids see the same snapshot), so its trajectories differ from 1.1.0 for the same seed.

### Fixed

- Docstrings of `DataCollector`, the orthogonal grids and `rescale_samples` render without
  reStructuredText errors; two tutorial notebooks regained their kernel metadata.

## 1.1.0 - 2026-10-22

### Added

- `docs/migrating_from_mesa.md`: a construct-by-construct map from Mesa 2.x and 3.x to Modelly
  (imports, agents, schedulers, grids, model, data collection, batch runs, events,
  visualization).
- `python -m modelly.migrate PATH [--write]`: a codemod that rewrites the mechanical parts
  (imports, agent constructors, scheduler attributes) and reports every line that needs a
  decision with the guide section to read.

### Verified

- The visualization and example test modules run green with warnings as errors, and the
  documentation builds.

## 1.0.0 - 2026-10-22

First release.

### Core

- `Model`: owns the scenario, both seeded random generators, simulation time and the event
  scheduler (`step`, `run_for`, `run_until`, `schedule_event`, `schedule_recurring`).
- `Agent` and `AgentSet`: ordered sets backed by a dict keyed on weak references, with `select`,
  `select_random`, `shuffle_do`, `do`, `map`, `get`, `set`, `agg`, `groupby`; views are built
  once and never hold strong references.
- `Column`: agent attributes stored in model-owned numpy arrays, one table per agent class, with
  `model.columns[Cls].<name>` views, `where(mask)` and `to_dataframe()`. Opt-in and transparent
  to per-agent code.
- `Scenario`: typed parameters plus the seed, with `spawn_replications` for reproducible sweeps.

### Space and time

- Discrete spaces: orthogonal Moore and Von Neumann grids, hexagonal grids, networks and Voronoi
  meshes, with per-cell neighbourhood caches, property layers backed by numpy arrays and an
  O(1) empty-cell index on grids.
- Continuous space with positions in one numpy array and vectorised distance queries.
- Event scheduler on a heap with lazy cancellation and compaction.

### Data and tooling

- `DataCollector` with model, agent, agent-type and table reporters; agent rows gathered
  column-wise and sliced straight from column tables when possible.
- Browser visualization (Solara), matplotlib and altair backends.
- Benchmarks for the bundled models, a performance audit (`docs/performance.md`), a guide to
  using Modelly in a project, the Pelloux engineering guidelines with a size audit and a local
  CI gate.
