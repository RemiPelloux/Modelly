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

## Columnar agent state

`modelly.columns` adds the one structural change with a large constant factor, as an opt-in.
A `Column` declared on an agent class stores that attribute in a numpy array owned by the
model (one table per concrete class, rows in insertion order, swap-remove on removal, the same
scheme the continuous space uses for positions). The agent reads and writes its own row through
a descriptor; the model reads everyone through `model.columns[Cls].<name>`, a zero-copy view.

Measured on the Boltzmann model with 10,000 agents, CPU time:

| Operation | Plain attribute | Column | Speedup |
|---|---|---|---|
| Gini coefficient | 1.09 ms | 0.03 ms | 33x |
| Count agents with `wealth > 0` | 0.94 ms | 0.008 ms | 125x |
| Mean wealth (`agg` vs `.mean()`) | 0.47 ms | 0.009 ms | 55x |
| Decrement every `wealth > 5` | 0.15 ms | 0.004 ms | 36x |
| Snapshot to a DataFrame | 1.10 ms | 0.31 ms | 3.6x |
| `AgentSet` of `wealth > 0` (`select` vs `where`) | 0.94 ms | 0.62 ms | 1.5x |
| `DataCollector.collect`, one attribute reporter | 0.95 ms | 0.46 ms | 2.1x |
| One `agent.wealth` read / `+= 1` inside `step` | 30 / 40 ns | 140 / 290 ns | 0.2x |
| Boltzmann `shuffle_do("step")`, object loop | 22.3 ms | 21.0 ms | within noise |

The last two rows are the trade-off: a single access costs a descriptor call and a numpy scalar
index instead of an instance-dict lookup. It does not show in the object loop because an agent
step touches the attribute a few times among far more expensive work, but a column is the wrong
home for a scratch value read in a tight loop. `where` is bounded by building the `AgentSet`
from 10,000 objects, not by the mask.

Recording a column with `DataCollector` is a straight slice of the table when the reporters are
all columns of one class and the collected agents are that class's whole population; rows are
then in table order rather than registration order (identical until an agent is removed).

## Continuous space

`get_agents_in_radius` compares one point against every position, so a model where every
agent asks for its neighbours is O(n²) per step. `ContinuousSpace.neighbors_within(radius)`
builds one `scipy.spatial.cKDTree` from the positions as they are now and queries it for the
whole population in a single call; on a torus the tree is periodic. A model uses it once per
step and gives every agent the same snapshot of positions (a simultaneous update).

| Boids, per step | Per-agent scans | One tree per step |
|---|---|---|
| 400 agents | 12.1 ms | 8.1 ms |
| 2,000 agents | 98.2 ms | 41.7 ms |
| 10,000 agents | about 2.5 s (extrapolated) | 227 ms |

What remains per agent is its own numpy arithmetic on a handful of neighbours.

## Agent lifecycle

Models with high birth and death rates (an insect population, an epidemic with recovery and
reinfection) spend much of their step creating and removing agents, so the framework's share
of such a model is the lifecycle path. Measured as a bare `Agent(model)` followed by
`agent.remove()`, and as the notebook agent below inside its real model:

| Birth + death | Mesa 2.3 | Modelly, first audit | Modelly now |
|---|---|---|---|
| bare agent, bare model | 372 ns | 861 ns | 421 ns |
| `agent in model.agents` (liveness check) | 35 ns | 160 ns | 35 ns |

What changed, in order: the `emit` decorator's wrapper checks for listeners inline and calls
`notify` only when someone can hear; `remove()` uses `try/except` instead of a
`contextlib.suppress` context manager (about 300 ns); the strong registry is a `dict` subclass,
so membership, length and the registry writes run in C; `Agent.__init__` and `Agent.remove`
inline the registration when the model keeps the default `register_agent` and
`deregister_agent` (a flag computed per class, with a test that an override is still honoured);
the cooperative `super().__init__()` is skipped for plain subclasses; the listener test is four
attribute reads with no dict lookups. A three-day bisect at 2,800 agents on the medfly model
below puts the current path at 11.4 ms against 11.7 ms for a stripped-down path with none of
Modelly's features and 11.2 ms for Mesa 2.3: the lifecycle is at parity.

### FastRandom

A quarter to a third of an agent-based model's time is the standard library's `random`, whose
`randint`, `choice`, `shuffle` and `sample` are Python loops calling `_randbelow` per draw.
`modelly.FastRandom` reimplements the four with the rejection loop written inline, making the
same `getrandbits` calls in the same order, so a seed gives exactly the same numbers as
`random.Random` (tested across seeds, sizes and both `sample` code paths). `model.random` is a
`FastRandom`. It is a small win: `shuffle` and `sample` are 18 to 20% faster, `randint` and
`choice` within noise, because the per-draw cost is the C call and the loop, not the method
dispatch.

### How we evaluate against other frameworks

Micro-benchmarks say where time goes; whether a framework is faster for a researcher is
decided on a real model. The method we use, and recommend for any comparison:

1. **Same model, same seeds.** Take a research notebook written for the other framework and
   port it with `python -m modelly.migrate`, changing nothing but the framework API. Seed both
   from the same value so the random streams match.
2. **Prove equivalence before timing.** Run both to completion and compare every output table
   by checksum. Only bit-identical outputs make the timings comparable; a port that changes
   the activation order or the random stream is a different model.
3. **Time CPU, pinned, alternating.** Wall-clock on a shared machine swings by 2x; CPU time of
   the experiment cell, in-process, pinned to one core, with the two frameworks alternating
   for at least three rounds, is stable to a few percent. Keep every round, not only the best.
4. **Profile both and compare shares.** The profiler inflates call-heavy code, so compare each
   function's share of its own run, and attribute the remainder by bisection: swap one piece
   for a minimal stand-in and measure again.

Applied to a medfly population model written for Mesa 2.3 (21 cells, a 576-season factorial
experiment, bit-identical output CSVs), the comparison went through two stages.

**Stage one: the model's own code.** The profile put 68% of the time in the notebook's model
code, 25% in `random` and 7% in Modelly. Three changes to the model, identical in both
notebooks and preserving the random stream (an early exit in the fruit status update placed
after its random draw, `len(self.slots) < capacity` instead of two property hops, and
re-filtering the free-fruit pool only on days when fruits were removed) cut the experiment
cell by 3x on both frameworks: Modelly 30 s to 9.4 s, Mesa 26 s to 7.8 s, same checksums.

A third round of model-code changes, again identical on both sides and stream-preserving (an
incremental rot score per fruit instead of a daily loop over its slots, an inlined capacity
test in the egg-laying loop, `FastRandom` seeding on the Modelly side), took the experiment
cell from 14.1 s to 11.2 s on Modelly and from 13.3 s to 11.0 s on Mesa, same checksums.
Dispatching the 576 independent seasons of the factorial to a forked process pool, records
reassembled in the original order so the CSV is identical, brings the cell to 1.3 to 1.6 s of
wall-clock on eight workers: the largest practical gain on this workload, and the one that
needs no re-validation of the model.

**Stage two: the framework.** On the optimised model, three pinned alternating rounds of the
experiment cell:

| Round | Mesa 2.3 | Modelly | Modelly, `FastRandom` in the port's seeding line |
|---|---|---|---|
| 1 | 13.39 s | 14.25 s | 13.98 s |
| 2 | 13.29 s | 13.97 s | 13.84 s |
| 3 | 13.47 s | 14.11 s | 13.88 s |

Modelly is 3 to 4% behind with the port's stdlib generator and 3% behind with its own, with
every per-agent primitive measured at or below Mesa's cost (birth and death, liveness check,
`random` and `time` reads), construction and data collection equal, and a three-day step at
peak population at parity. The remainder is diffuse and below what this machine can resolve.
We call that parity, not a win, and the comparison harness stays outside the repository.

Measured and rejected on this workload: a `shuffle` that draws its random words in one call
(it reproduces the permutation but leaves the stream in a different place for the next draw,
and is 3x slower); a cheaper `Model` construction (it is 18 µs; 576 of them are 10 ms).

### The playbooks: same model, each framework's own idiom

The port above answers "what does identical code cost". The second question is what each
framework lets a modeller write. `benchmarks/playbooks/` holds five models implemented twice,
for Mesa 2.3 with per-agent methods on `MultiGrid`, `ContinuousSpace` and `NetworkGrid`, and
for Modelly with `Column` state, `CellIndex` (integer rows for the cells of any discrete space
plus their sparse adjacency), `Occupancy` / `claim`, `pairs_within` / `move_all` and
`ColumnTable.thin`. The rules for a fair comparison, enforced by the runner:

1. Same model: same rules, same synchronous phase order, same parameters, same graph and
   initial positions where seeds can be shared; the Mesa side uses numpy where a Mesa modeller
   would.
2. Agreement in distribution, checked: every implementation runs the same seeds and each
   summary statistic is compared with the Mesa reference by Welch's t-test (flagged below
   0.01). The implementations draw their random numbers in different orders, so the outputs
   differ run by run and must agree in law; `vectorised_phases.md` states why each vectorised
   phase has the law of its per-agent loop.
3. Determinism, checked: the first seed runs twice per implementation. (This check caught the
   Mesa side being unseeded when the seed was passed positionally: Mesa 2.3 reads it from the
   keyword arguments in `Model.__new__`.)
4. CPU time of a fresh interpreter per run, build and steps timed separately, pinned to one
   core, implementations alternating over three rounds, every round reported.

Median CPU seconds of the steps at the large size on this machine:

| Playbook | Agents | Mesa 2.3 | Modelly, cell lists | Modelly, columns | Speed-up |
|---|---|---|---|---|---|
| Grid epidemic, 60 steps | 20,000 | 10.5 s | 6.7 s | 0.10 s | 110x |
| Predator-prey with grass, 200 steps | ~5,500 | 5.4 s | 5.0 s | 0.63 s | 8.5x |
| Flocking, 50 steps | 4,000 | 30.9 s | | 0.61 s | 50x |
| Virus on a network, 100 steps | 30,000 | 10.8 s | | 0.31 s | 35x |
| Insect population, individuals, 120 days | ~26,000 | 6.9 s | | 1.47 s | 4.7x |
| Insect population, cohorts | ~26,000 | 6.9 s | | 0.02 s | 330x |

The "cell lists" column is the same model with Mesa's data structure, every cell holding the
list of its agents, so movement and predation stay per-agent loops: 1.1 to 1.6x, consistent
with the port. The gap opens when the cell becomes a column of rows: the random walk is one
`random_neighbor` call over the grid's CSR adjacency, the exposure count a `bincount`, the
predation a vectorised matching with the law of the shuffled sequential rule. Construction is
reported separately (a 180x180 Moore grid builds in 0.11 s, a 30,000-node network in 0.4 s,
against milliseconds for Mesa's lazy structures); the build+run speed-ups in the results are
correspondingly lower (29x, 6.5x, 49x, 11x, 4.7x, 305x).

The insect playbook is a stage-structured population under sterile releases, an original
model with the dynamics of the medfly workload (thousands of eggs a day, stage-specific
mortality, density-dependent larval survival). Agent creation is at parity, so the
individual-level gap is the per-agent loop only (4.7x). The cohort variant represents every
insect in the same (stage, age, sex) class as one row and thins it with a binomial draw; it
has the same law as the individual model (the agreement table shows it) and runs in 20 ms. The machine was under heavy load
during these rounds; absolute times vary by up to 2x between sessions, the ratios do not.

## Caches

Two results are now reused instead of recomputed:

- `DataCollector.get_agent_vars_dataframe` keeps the frame it last built and the number of
  steps it covered; a later call converts only the new steps and appends them. A dashboard
  that reads the frame every tick pays for one tick of rows instead of the whole history.
- `ContinuousSpace.neighbors_within` keys its lists on the radius, the population size and a
  hash of the position array, so repeated queries within a step cost a hash of the positions
  (tens of microseconds for 10,000 agents) instead of a tree build, and any position change,
  including a direct write to the array, invalidates it.

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

1. **Vectorised movement on grids** is in: a cell-row column plus `CellIndex.random_neighbor`
   moves a whole population in one call, and `Occupancy` / `claim` answer the per-cell
   questions a step still has. What remains is a visualisation path for agents that keep
   their cell as a column rather than in the cell's list.
2. **Shared-memory replications.** `workers=` runs replications in processes that each hold a
   full model; a shared column store would let a sweep over one large model fan out without
   copying it.
3. **Compiled hot loops.** The remaining per-agent cost is Python call overhead on the cell move
   and the neighbourhood lookup; an optional compiled path for those two would be the last
   large win before a different authoring model.

## How to re-run

```bash
python benchmarks/global_benchmark.py        # the four reference models, saves timings_N.pickle
python benchmarks/compare_timings.py a.pickle b.pickle
python benchmarks/playbooks/compare.py --core 5   # the five playbooks against Mesa 2.3
```
