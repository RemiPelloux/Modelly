# Changelog

All notable changes to Modelly. The format follows Keep a Changelog; versions follow semantic
versioning.

## 1.0.0 - 2026-10-24

First release.

### Core

- `Model`: owns the scenario, both seeded random generators, simulation time and the event
  scheduler (`step`, `run_for`, `run_until`, `schedule_event`, `schedule_recurring`).
- `Agent` and `AgentSet`: ordered sets with `select`, `select_random`, `shuffle_do`, `do`,
  `map`, `get`, `set`, `agg`, `groupby`; the model's registries are `dict`-backed (membership
  in C), views never hold strong references, and birth and death skip every listener check
  when nobody observes the model.
- `Column`: agent attributes stored in model-owned numpy arrays, one table per agent class,
  with whole-population views (`model.columns[Cls].<name>`), `draw`, `do_where`,
  `remove_where`, `where`, `thin` and `to_dataframe`; per agent, a column is a fast property
  reading the row through a `memoryview` (27 ns per read). `Agent.column_specs()` lists them.
- `Scenario`: typed parameters plus the seed, with `spawn_replications` for reproducible sweeps.

### Random numbers

- `FastRandom` (`model.random`): exactly the standard library's numbers for a seed, faster.
  A compiled core (`modelly/_native/fastrng.c`) runs `randint`, `choice`, `shuffle`, `sample`
  and `_randbelow` in C on CPython's own Mersenne Twister state (`randint` 59 ns against 193 ns,
  `shuffle` 38 ns against 206 ns per element), verified against `random.Random` at import; the
  pure-Python `PyFastRandom` is the fallback.

### Space and time

- Discrete spaces: orthogonal Moore and Von Neumann grids, hexagonal grids, networks and Voronoi
  meshes, with per-cell neighbourhood caches, property layers backed by numpy arrays and an
  O(1) empty-cell index.
- `CellIndex`: integer rows and a sparse adjacency for any discrete space (`counts`,
  `neighbor_sum`, `random_neighbor`), `Occupancy` and `claim` for cell membership as a column,
  and `track` to list and draw agents placed by a row column.
- Continuous space with positions in one numpy array, one KD-tree per step for neighbour
  queries (`neighbors_within`, `pairs_within`) and `move_all`.
- Event scheduler on a heap with lazy cancellation and compaction.

### Populations and experiments

- `CohortTable`: counted populations (one row per state, no agent objects) with binomial
  `thin`, `split` and `draw`, `merge` and `compact`, with the law of the individual model.
- `run_batch` and `run_grid`: experiments over processes with results in the sequential
  order and one `SeedSequence` seed per run.

### Data and tooling

- `DataCollector` with model, agent, agent-type and table reporters; agent rows gathered
  column-wise and sliced straight from column tables when possible.
- Browser visualization (Solara), matplotlib and altair backends.
- `python -m modelly.migrate`: a codemod and guide for models written for Mesa.
- `python -m modelly.lint`: static checks for models (random draws outside the model's
  generators, missing `super().__init__`, population scans and more).
- Benchmarks: the bundled reference models, five playbooks written for Mesa 2.3 and for
  Modelly with an agreement and determinism check, and the evaluation method in
  `docs/performance.md`. On a research model ported line for line from Mesa 2.3, Modelly is
  12% faster with bit-identical output; written with columns and cohorts, the playbooks run
  4.3 to 213 times faster.
- Platform wheels for Linux and macOS with the compiled core, a pure wheel and the sdist for
  every other platform.
