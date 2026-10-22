# Changelog

All notable changes to Modelly. The format follows Keep a Changelog; versions follow semantic
versioning.

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
