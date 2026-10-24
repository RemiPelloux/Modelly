# Changelog

All notable changes to Modelly. The format follows Keep a Changelog; versions follow semantic
versioning.

## 1.1.0 - 2026-10-24

### Added

- `modelly.profile`: a runtime profiler. `with Profiler(model) as prof: model.run_for(n)`, then
  `prof.report()` or `prof.to_dataframe()`, gives the time of each step by agent class and
  method (calls, agents per call, microseconds per agent), data collection and scheduled events,
  with hints that point at the matching lint rule. `python -m modelly.profile model.py:MyModel`
  runs it from the command line. Results are identical with and without the profiler, and the
  instrumented methods are restored exactly on exit.
- `python -m modelly` and a `modelly` script: one entry point for `lint`, `migrate` and `profile`,
  with `--version` and a help page listing every command.
- `AgentPortrayalStyle.filled` (Altair backend); extra keywords to `draw_agents` reach
  `mark_point` instead of being dropped.
- Three benchmark playbooks, each for Mesa 2.3 and Modelly with agreement and determinism
  checks: `schelling` (27x), `boltzmann_wealth` (7.4x) and `sugarscape` (12x).

### Linter

- New rules: MDL005 wall-clock or OS entropy in model code, MDL006 ordering by `id()` or
  `hash()`, MDL007 removing agents while looping over the population, MDL008 `global` state in
  a model method, MDL009 editing `model.agents` directly, MDL106 DataFrames built inside `step`,
  MDL107 a per-agent loop that only writes columns.
- MDL001 also catches unseeded `Random()`, `SystemRandom` and numpy generators without a seed,
  and resolves imports (`default_rng(seed=7)` is no longer flagged); MDL004 skips `__slots__`
  and `ClassVar`.
- `# noqa: MDLxxx` suppression, `[tool.modelly.lint]` in `pyproject.toml` (`select`, `ignore`,
  `per-file-ignores`), `--explain CODE` with a bad and a fixed example, `--statistics`,
  `--format github` and `--quiet`.
- Detailed `--help` for `lint` and `migrate`, with examples and exit codes; `docs/lint.md`
  lists every rule.

### Performance

- Moving an agent between cells runs in a third compiled module (`modelly/_native/fastcell.c`):
  one move is 205 ns to 107 ns, the cell-list playbooks 7 to 14% faster, with the same results.
  Subclasses that override `add_agent` or `remove_agent` keep their overrides; the pure-Python
  twin is used when the module is not built.
- `import modelly` no longer walks the stack to name its loggers (about 30 ms less).

### Fixed

- Matplotlib marker groups are drawn in first-seen order instead of set order, so the
  layering no longer changes from run to run.
- `run_batch` no longer emits Python's multi-threaded fork `DeprecationWarning` for closure
  batches.

### CI

- Release wheels are built on tags and manual runs only; superseded runs are cancelled;
  docs-only changes skip the build; Dependabot groups its updates monthly; the `examples` job,
  which checked out a missing repository, is gone (the test matrix already runs `tests/examples`).

## 1.0.1 - 2026-10-24

The 1.0.0 code, published to PyPI under a new number: PyPI does not accept a second upload of
1.0.0, and its `modelly-abm 1.0.0` predates the domain package layout.

## 1.0.0 - 2026-10-24

First release.

### Package layout

Every module lives in a domain package; the top-level names (`modelly.Agent`, `modelly.Model`,
`modelly.DataCollector`, `modelly.Column`, `modelly.CohortTable`, `modelly.FastRandom`,
`modelly.run_batch`, `modelly.run_grid`) are the short way in.

| Package | Contents |
|---|---|
| `modelly.core` | `agent`, `model`, `agentset`, `columns`, `rng`, `exceptions` |
| `modelly.space` | discrete spaces; `modelly.space.continuous` |
| `modelly.time` | `schedule`, `signals` |
| `modelly.data` | `collector`, `reporters`, `recorders` |
| `modelly.behaviour` | `actions`, `states`, `meta_agents` |
| `modelly.scenarios` | scenarios |
| `modelly.batch` | `runs`, `cohorts` |
| `modelly.viz` | `solara`, `console`, `render`, `altair`, `mpl` |

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
- `do` and `shuffle_do` on the model's agent registries, and the breadth-first walk behind
  `Cell.get_neighborhood`, run in a second compiled module (`modelly/_native/fastloop.c`),
  with an identical pure-Python twin used when it is not built (`MODELLY_PURE_PYTHON=1`).

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

### Internals

- Every module is at most 300 lines and every function body at most 25 lines, except the
  per-agent render loop of the Altair backend, kept inline on purpose.
- Tests mirror the package layout; `tests/native` runs the compiled loops against their twins.
