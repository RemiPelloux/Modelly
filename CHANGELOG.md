# Changelog

All notable changes to Modelly. The format follows Keep a Changelog; versions follow semantic
versioning.

## 1.5.2 - 2026-10-23

### Added

- A compiled random core, `modelly/_native/fastrng.c`: `randint`, `choice`, `shuffle`,
  `sample` and `_randbelow` in C on CPython's own Mersenne Twister state, identical streams to
  `random.Random` (verified at import and by tests over interleaved draws of every method).
  `randint` 193 to 59 ns, `choice` 190 to 72 ns, `shuffle` 206 to 38 ns per element. On the
  reference Mesa 2.3 workload, same model code and identical output, Modelly is now 12%
  faster. `FastRandom` falls back to the pure-Python `PyFastRandom` without the extension, on
  free-threaded builds, or with `MODELLY_PURE_PYTHON=1`.
- Platform wheels: a hatch build hook (`hatch_build.py`) compiles the core into the wheel; the
  release workflow builds Linux x86-64 and ARM and macOS wheels with cibuildwheel for CPython
  3.12 to 3.15, plus a pure wheel and the sdist. `scripts/build-native.sh` builds it in place.
- `modelly.CohortTable`: a counted population (one row per state, no agent objects) with
  binomial `thin`, `split` and `draw`, `compact`, `merge`, `totals_by` and `to_dataframe`.
  The insect playbook's cohort variant now uses it: 213x faster than the individual Mesa model.
- `modelly.run_batch` and `modelly.run_grid`: parallel runs with results in task order (the
  output equals the sequential loop's), per-run seeds from `SeedSequence.spawn`, notebook
  functions and closures supported on Linux, `MODELLY_WORKERS` to set the pool size.

- `CellIndex.track(model, agent_class, column="row")`: agents that keep their cell as a row
  column are listed by `space.agents` and drawn by the visualisation at
  `index.cells[agent.<column>]`; `CellIndex.cell_of(agent)` returns that cell.
- `Agent.column_specs()`: the `Column` declarations of a class, in table order.

### Changed

- A `Column` attribute is now a plain `property` on its class reading the agent's row through
  a `memoryview`: a read went from 79 ns to 27 ns and `+= 1` from 171 ns to 72 ns, and a
  Boltzmann step over 5,000 column agents from 5.0 ms to 3.1 ms. Reads return Python `int`,
  `float` and `bool` instead of numpy scalars; strings, objects, complex and datetimes keep
  numpy indexing, and writes a `memoryview` rejects fall back to numpy's assignment.
- On the class, a column attribute is that property (its docstring is the column's repr), not
  the `Column` declaration; use `AgentClass.column_specs()["name"]` for the dtype and default.

## 1.5.1 - 2026-10-23

### Changed

- `import modelly` no longer loads scipy: `KDTree`, `cKDTree` and `cdist` are imported where a
  hex grid, network, Voronoi mesh or continuous-space query first needs them. Importing the
  package went from 0.38 s to 0.28 s; a test keeps scipy out of the import.

## 1.5.0 - 2026-10-23

### Added

- `modelly.discrete_space.CellIndex`: integer rows for the cells of any discrete space and
  the sparse (CSR) adjacency built from their connections, with `counts` (per-cell totals),
  `neighbor_sum` (one matrix-vector product), `random_neighbor` (a vectorised random walk)
  and `to_layer`. `cell.index` is the row.
- `modelly.discrete_space.Occupancy` and `claim`: who is in which cell from a row column,
  by one sort per step, and a vectorised "each claimant takes one distinct member of its
  cell" matching with the law of the shuffled sequential rule (tested).
- `ColumnTable.thin`: binomial thinning of a count column, the cohort (super-individual)
  form of per-individual survival. Assigning `table.<column>` now writes the live rows in
  place, so `table.energy -= 1` is safe.
- `modelly.experimental.continuous_space.pairs_within`, `difference_vectors` and
  `move_all`: the neighbour relation as index pairs from one periodic KD-tree,
  torus-corrected pair vectors, and a whole-population move.
- `benchmarks/playbooks/`: five models written twice, for Mesa 2.3 and for Modelly, with a
  runner that times both in their own environments, pinned and alternating, checks the
  implementations agree by Welch's t-test over shared seeds and checks determinism.
  `docs/vectorised_phases.md` states the equivalence arguments behind each vectorised phase
  and the cohort compression.
- `modelly.FastRandom`: a `random.Random` whose `randint`, `choice`, `shuffle` and `sample`
  make exactly the standard library's `getrandbits` calls with fewer Python calls; identical
  streams for a seed, verified by tests. `model.random` is one.

### Changed

- The strong agent registry (`model.agents`, `model.agents_by_type[...]`) is a `dict`
  subclass: membership, length and registration run in C; `agent in model.agents` went from
  160 ns to 35 ns.
- `Agent.__init__` and `Agent.remove` inline registration when the model keeps the default
  `register_agent`/`deregister_agent` (overrides are still honoured, tested), skip the no-op
  cooperative `super().__init__()` for plain subclasses, and test for signal listeners with
  four attribute reads. The lifecycle is at parity with Mesa 2.3 on a lifecycle-heavy model.
- Model reporters are compiled once at registration instead of dispatched on every collect.
- Event scheduling and time advance live in `modelly.scheduling.HasSchedule`, mixed into
  `Model`, so `model.py` stays under its size limit.
- A matplotlib frame no longer builds a weak set or allocates a numpy array per agent.
- `FastRandom` is faster than `random.Random` on every overridden draw on CPython 3.15:
  `randint` (type checks the interpreter specialises instead of `operator.index`, a bit-length
  table), `choice`, `sample` (no `Sequence` ABC check for `list`, `tuple`, `range`) and
  `shuffle` (runs of constant bit length above 64 elements). Streams unchanged, tested across
  every run boundary.
- Agent birth and death take one model flag (`_quiet`) and one class flag (`_extra_hooks`)
  instead of six attribute reads when nobody listens and the registry is the default; the
  flag only ever turns false, so listeners, batches, suppression and overridden
  `register_agent` keep their exact behaviour (tested).
- On the reference Mesa 2.3 workload (same model code, bit-identical outputs), Modelly is now
  1.3 to 3.8% faster at default settings with `FastRandom` in the port's seeding line.
- Grid construction writes cell connections directly (no per-connection method call or
  cache clear on fresh cells): a 180x180 Moore grid builds in 0.11 s instead of 0.17 s.

- The Mesa 2.3 comparison harness is no longer in the repository; `docs/performance.md`
  describes the evaluation method and keeps the measured numbers.
- Documentation site on GitHub Pages, citation metadata, README and contributing guide refresh.

## 1.4.0 - 2026-10-22

### Added

- `benchmarks/notebooks/`: four generated benchmark notebooks (grid epidemic with columns,
  predator-prey lifecycle, flocking with one tree versus per-agent scans, virus on a network)
  at three sizes each, a generator (`make_notebooks.py`) and a headless runner
  (`run_notebooks.py`) that executes them and writes `results/README.md`.

### Changed

- A matplotlib frame no longer allocates a numpy array per agent for grid positions, builds a
  weak `AgentSet` of the whole population, or pays a union-type `isinstance` per style: a frame
  of 8,000 agents went from 26 ms to 19.5 ms of CPU (warm caches, best of seven).

## 1.3.2 - 2026-10-22

### Added

- `benchmarks/mesaVSmodelly/`: the same-notebook comparison against Mesa 2.3 (port script,
  headless runner with per-cell timing and CSV checksums, compare and smoke scripts, both
  notebooks as fixtures). Run it with `.venv/bin/python benchmarks/mesaVSmodelly/compare.py`
  once a Mesa 2.3 environment exists at `.venv-mesa2`.

## 1.3.1 - 2026-10-22

### Changed

- Agent birth and death are 37% cheaper (861 ns to 549 ns for the pair): the `emit` wrapper
  checks for listeners inline and calls `notify` only when it would have an effect, `remove()`
  no longer builds a context manager, the registries are written directly, and empty dataset
  loops are skipped. Signal semantics are unchanged; `Model.observe("agents", ...)` still fires.
- Documenting a change that shipped in 1.3.0: `Model.time` is a plain attribute (reads are
  about three times cheaper than through the observable descriptor); `_set_time` emits the
  CHANGED signal once per time advance, so `observe("time", ...)` and data recorders keep
  working. The registration debug log lines are gone.
- A same-notebook benchmark against Mesa 2.3 (`benchmarks/mesaVSmodelly/`, bit-identical
  outputs) runs at parity to about 1.15x in Modelly's favour, best of three alternating runs.

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
