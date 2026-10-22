# Changelog

All notable changes to Modelly. The format follows Keep a Changelog; versions follow PEP 440.

## 4.0.0a1 - 2026-10-22

First tagged release of Modelly. Performance audit of the core data structures, columnar agent
state, the Pelloux engineering guidelines, and a README and documentation rewrite.

### Added

- `modelly.columns`: `Column` attributes stored in model-owned numpy arrays, one `ColumnTable`
  per agent class with `model.columns[Cls].<name>` views, `where(mask)` and `to_dataframe()`.
  Opt-in; classes without a `Column` are untouched.
- `docs/performance.md`: the audit, before/after measurements, and the ideas measured and
  rejected.
- `docs/using_modelly_in_your_project.md`: end-to-end guide from an empty folder to a tested,
  replicated model.
- `example.py`: the runnable README model.
- Pelloux guidelines (`pelloux-guidelines.md`) with `scripts/ci-local.sh`,
  `scripts/audit-pelloux.sh`, `scripts/seed-pelloux-baseline.sh` and `pelloux-baseline.json`.

### Changed

- `AgentSet` is backed by a dict keyed on `weakref.ref` instead of `WeakKeyDictionary`; bulk
  operations walk a snapshot, so mutating a set while iterating no longer raises.
- Views from `model.agents` (`select`, `shuffle`, `sort`, `groupby`, `select_random`) are built
  once and always return a weak `AgentSet`.
- `Cell` neighbourhoods are cached per cell; `connect`/`disconnect` invalidate only that cell.
- `Grid.select_random_empty_cell` uses a lazily built O(1) index of empty cells; on a dense grid
  the chosen cells differ from 4.0.0a0 for the same seed (runs stay reproducible per seed).
- `DataCollector` gathers agent rows column-wise and copies only mutable values.
- `modelly.modelly_logging` is `modelly.log`; `modelly.experimental.modelly_signals` is
  `modelly.experimental.signals`.
- `modelly.agentset` is a package; `modelly.discrete_space.grid` is split into `base_grid`,
  `grid` and `property_layer`; reporter plumbing lives in `modelly.reporters`.
- The Boltzmann example stores `wealth` as a `Column` and computes Gini in numpy.

### Fixed

- Discarded grids are freed: the neighbourhood cache was process-global and a grid's cell class
  was registered in the global `copyreg` table.
- Unpickled grids re-home every cell onto one class, so property-layer accessors work on all
  cells, not only the first.
