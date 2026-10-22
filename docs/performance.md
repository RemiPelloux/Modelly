# Performance audit

This page records how Modelly's core data structures were audited, what was measured, what
changed, and what is still on the table. Numbers come from the benchmark configurations in
`benchmarks/configurations.py` ("large" sizes) and from micro-benchmarks run on the same
machine, best of several alternating before/after runs, measured in CPU time.

## The question

Modelly keeps one Python object per agent and stores collections of them in dictionaries:
`AgentSet` was a `weakref.WeakKeyDictionary`, the model registry is a plain `dict`, and a cell
holds a `list` of the agents standing on it. Is that the right shape, and where does the time go?

The short answer: the shapes are right for the operations a simulation performs (ordered
membership, O(1) removal, stable shuffles), but four things around them were costing far more than
the containers themselves. Those were fixed. The one structural change with a large constant
factor (columnar agent state) is a roadmap item, not a patch.

## What the profile showed

Profiling the four benchmark models at their "large" configuration put the framework's own
overhead in five places, in order of cost:

1. **Empty-cell search on dense grids.** `Grid.select_random_empty_cell` tried 50 random cells,
   then fell back to `np.argwhere` over the whole grid, on every call. On a 99% full grid that is
   14 µs per call, and a Schelling model at that density spends most of its step there.
2. **Per-agent data collection.** `DataCollector` built one closure call per reporter per agent,
   read `agent.model.time` through the observable descriptor for every agent, and called
   `deepcopy` on `None` and numpy scalars. About 390 ns per agent per step.
3. **Double-built views.** Every `select`, `shuffle`, `sort` and `groupby` on `model.agents`
   built a strong-reference set and then rebuilt it as a weak one. Counting fully grown grass in
   Wolf-Sheep built a 10,000-entry weak dictionary to call `len()` on it: 2.2 ms of a 17 ms step.
4. **`WeakKeyDictionary` overhead.** Its pure-Python wrapper and iteration guard made construction,
   membership and iteration about twice the cost of a dict keyed on `weakref.ref` objects.
5. **Unconditional property-layer writes.** Every agent move wrote the `empty` layer twice through
   a numpy scalar index, even when the cell's emptiness had not changed.

Two defects came out of the same pass:

- `Cell.get_neighborhood` was decorated with `functools.cache` on a method, which is one global
  cache keyed on the cell. Discarding a grid left all its cells alive (10,000 cells after building
  and dropping fifteen 100x100 grids), and `connect()` on any cell cleared every cell's cache in
  the process.
- `Grid.__init__` registered each grid's private cell class in the global `copyreg` dispatch
  table, so a discarded grid stayed reachable from it.

## What changed

| Area | Before | After |
|---|---|---|
| `AgentSet` storage | `weakref.WeakKeyDictionary` | `dict` keyed on `weakref.ref` with a removal callback; all bulk operations walk a C-level snapshot of the keys |
| Views from the registry | built strong, rebuilt weak | built once through `_view()` |
| `select` | generator with a running count | list comprehensions, slice for `at_most` |
| `get` | Python loop | `operator.attrgetter` |
| Neighbourhood cache | global `functools.cache` | per-cell `dict`; `connect`/`disconnect` clear only that cell |
| Empty cells | 50 tries then full scan | 8 tries, then a lazily built swap-remove index kept in sync by `cell.empty` |
| `empty` layer writes | on every add/remove | only on empty/occupied transitions |
| Agent rows | closure per reporter per agent | gathered column-wise: one C-level `map` per reporter, columns zipped into rows; copy a column only if it holds a mutable value |
| Grid cell class pickling | global `copyreg` registration | `__reduce__` on the class |
| Grid unpickling | one class per cell, accessors on the first | cells re-homed onto one class, accessors restored on it |
| Registration logging | f-string built even when debug is off | lazy `%s` formatting |
| Wolf-Sheep grass reporter | `len(select(...))` | a direct count |

## Measurements

Model benchmarks, CPU time per step, best of three alternating rounds:

| Model (large) | Before | After | Speedup |
|---|---|---|---|
| Boltzmann wealth, 10k agents, 100x100 | 19.3 ms | 16.6 ms | 1.16x |
| Schelling, 100x100, density 0.8, radius 2 | 26.9 ms | 24.4 ms | 1.10x |
| Schelling, 100x100, density 0.98 | 137.7 ms | 20.7 ms | 6.66x |
| Wolf-Sheep, 100x100, 1000 sheep, 500 wolves | 18.5 ms | 17.0 ms | 1.09x |
| Boids, 400 agents | 12.4 ms | 12.1 ms | 1.03x |

Hot paths, per call:

| Operation | Before | After |
|---|---|---|
| `select_random_empty_cell`, 99% full grid | 14.3 µs | 0.11 µs |
| `select_random_empty_cell`, 50% full grid | 0.29 µs | 0.14 µs |
| agent move between two cells | 522 ns | 440 ns |
| `cell.get_neighborhood(radius=2)` (cached) | 77 ns | 52 ns |
| `cell.neighborhood` (cached) | 49 ns | 56 ns |
| build a 10k-agent `AgentSet` | 0.83 ms | 0.49 ms |
| `model.agents.select(...)` over 10k agents | 1.98 ms | 1.30 ms |
| `DataCollector.collect`, 10k agents, 1 attribute | 1.60 ms | 0.95 ms |
| `DataCollector.collect`, 10k agents, 2 attributes + 1 lambda | 2.13 ms | 1.43 ms |
| Wolf-Sheep `collect` (grass count) | 2.2 ms | 0.4 ms |
| cells alive after discarding 15 grids | 10,000 | 0 |

The remaining per-step cost in Boltzmann and Schelling is the agents' own Python logic
(random choices, list comprehensions over neighbours), which is the expected profile for an
object-per-agent engine.

## Considered and rejected

Measured on the same machine; each would have bought a few percent at the cost of complexity or
of a different random stream for the same seed.

| Idea | Measured | Why not |
|---|---|---|
| Shuffle 10k agents with a numpy permutation seeded from the stdlib stream | 810 µs to 310 µs per shuffle, about 3% of a 10k-agent step | needs a size threshold (slower below ~500 agents) and changes which order a seed produces |
| `cells[int(random() * n)]` instead of `random.choice` | 100 ns to 50 ns per pick | changes the random stream for every model for a 3% gain |
| Empties index with a slot stored on each cell instead of a dict | 90 ns to 70 ns per move | couples `Cell` to the grid index for 20 ns |
| Return `Cell.agents` without copying | 60 ns per access | callers that remove agents while iterating would skip elements |

The remaining per-agent framework cost in the grid models is about 0.6 µs of a 1.4 µs
agent-step (the cell move, the neighbourhood lookup, the shuffle and the membership check);
the rest is the agent's own logic. Going meaningfully faster from here means the columnar
state on the roadmap, not more micro-tuning.

## Behaviour notes

- Seeded runs that call `select_random_empty_cell` on a dense grid draw from the index instead of
  from repeated random tries, so the sequence of chosen cells differs from earlier versions for the
  same seed. Runs are still fully reproducible for a given seed.
- Iterating an `AgentSet` walks a snapshot: adding or removing agents while iterating no longer
  raises, and `do`/`shuffle_do`/`map` still skip agents removed earlier in the same pass.
- `select_random` and `select` on `model.agents` now return a weak `AgentSet` like every other view
  (previously `select_random` leaked a strong-reference set).

## What is next

These are the changes with the largest remaining upside. Each is a project, not a patch.

1. **Columnar agent state.** Keep the `Agent` authoring model but store declared attributes in
   numpy columns owned by the model, so reporters, aggregations and filters run as array
   operations. This is the step that turns data collection and `agg` from microseconds per agent
   into nanoseconds.
2. **Spatial index for continuous space.** `get_agents_in_radius` is O(n) per query, so a flocking
   model is O(n²) per step. A grid hash or a `cKDTree` rebuilt once per step makes it O(n log n).
3. **Empty-cell index for non-grid spaces.** `DiscreteSpace.empties` on networks and Voronoi meshes
   still scans every cell; the grid index can be generalised once those cells get a space hook.
4. **Parallel replications.** `Scenario.spawn_replications` already yields independent seeded
   scenarios; running them across processes is plumbing, not research.

## How to re-run

```bash
python benchmarks/global_benchmark.py        # the four reference models, saves timings_N.pickle
python benchmarks/compare_timings.py a.pickle b.pickle
```
