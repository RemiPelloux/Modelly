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

`modelly.core.columns` adds the one structural change with a large constant factor, as an opt-in.
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
| One `agent.wealth` read / `+= 1` inside `step` | 6 / 13 ns | 27 / 72 ns | 0.2x |
| Boltzmann `shuffle_do("step")`, object loop | 22.3 ms | 21.0 ms | within noise |

The last two rows are the trade-off. A column attribute is a plain `property` installed on the
class (the interpreter inlines property getters, which it never does for a custom descriptor)
that reads the agent's row through a `memoryview`, so a read returns a Python `int`, `float` or
`bool` rather than building a numpy scalar, and arithmetic on it is Python arithmetic. That took
a read from 79 ns to 27 ns and `+= 1` from 171 ns to 72 ns (CPython 3.15), and a Boltzmann
exchange step over 5,000 column agents from 5.0 ms to 3.1 ms, against 1.6 ms with plain
attributes. Dtypes a `memoryview` cannot index (strings, objects, complex, datetimes) keep
numpy indexing, and a write a `memoryview` rejects (a float into an int column) falls back to
numpy's own assignment, so values and errors are unchanged. A column is still not the place for
a scratch value read in a tight loop. `where` is bounded by building the `AgentSet`
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
`FastRandom`. On CPython 3.15, against a standard library that has itself become cheaper,
per call:

| Draw | Faster than `random.Random` by | How |
|---|---|---|
| `randint(6, 11)` | 3 to 4% | `type(x) is int` (specialised by the interpreter) instead of two `operator.index` calls; bit length from a 4,096-entry table instead of `int.bit_length()` |
| `choice` | 11 to 12% | the same table |
| `sample(list of 3,000, 3)` | 20 to 26% | the table, and the `Sequence` ABC check skipped for `list`, `tuple` and `range` |
| `shuffle(3,000)` | 15 to 27% | lists over 64 elements are walked in runs of constant bit length, so the inner loop has no lookup at all |

Every change makes the same `getrandbits` calls in the same order; a test shuffles every
length from 0 to 139 and lengths around each power of two and compares with the standard
library element for element, and then compares the next draw.

**The compiled core.** Pure Python had nothing left to remove: what remained of a draw
was the Python function call around a C call. `modelly/_native/fastrng.c` implements
`randint`, `choice`, `shuffle`, `sample` and `_randbelow` in C as "fastcall" methods (the
cheapest call CPython has). The type extends `_random.Random` and generates words from the same
Mersenne Twister state the base class uses, so `random()`, `gauss`, `getrandbits`, `seed` and
`getstate` from the standard library and the compiled methods consume one stream exactly as
`random.Random` does; the stdlib's `sample` set-size rule and both of its code paths are
reproduced draw for draw. Anything outside the fast paths (ranges of 2³² or more, non-int
arguments, sequences that are not lists or tuples, `counts=`) goes to the standard library's
own code, which reads the same state. At import a self-test compares a mixed sequence of draws
with `random.Random`; on any mismatch, without a compiler, or with
`MODELLY_PURE_PYTHON=1`, `FastRandom` is the pure-Python `PyFastRandom` above. Per call:

| Draw | `random.Random` | `PyFastRandom` | compiled `FastRandom` |
|---|---|---|---|
| `randint(6, 11)` | 193 ns | 185 ns | 59 ns |
| `choice(list of 3,000)` | 190 ns | 168 ns | 72 ns |
| `shuffle(3,000)`, per element | 206 ns | 156 ns | 38 ns |

Assembly would not beat this: generating a word is 2 to 3 ns of C that compilers already turn
into near-optimal code, and the rest is the interpreter's call, which no language can avoid.
Platform wheels carry the compiled modules (Linux glibc and musl on x86-64 and ARM64, macOS,
Windows x86-64 and ARM64, the GIL and the free-threaded interpreters); other platforms install
the pure wheel.

A second compiled module, `modelly/_native/fastloop.c`, runs `do` and `shuffle_do` on the
model's agent registries and the breadth-first walk behind `Cell.get_neighborhood`. Each loop
has an identical pure-Python twin in `modelly/_native/loops.py`, used when the module is not
built or `MODELLY_PURE_PYTHON=1` is set; `tests/native` checks the two against each other.

A third, `modelly/_native/fastcell.c`, is the setter of `CellAgent.cell`: add to the new cell
(capacity check, `CellFullException`), remove from the old one (`AgentMissingException` chained
from the `ValueError`), and write `empty` only on a transition, through the normal attribute
protocol so a grid's property-layer `empty` still updates. It runs `Cell.add_agent` and
`remove_agent` inline only when the cell's type resolves them to `Cell`'s own (checked per type,
revalidated on CPython's type version tag, so an override or a later patch is called instead),
and reads the `_agents` and `capacity` slots at their offsets. Its twin is `py_set_cell` in
`modelly/_native/cells.py`. A first version that used plain attribute lookups was no faster than
Python 3.15's specialised bytecode; the slot reads are what made the difference.

Measured on Python 3.15, one pinned core (`nice taskset -c 5`) of a shared 16-core laptop at
load 3 to 4, CPU time, base (`main`) and new alternating in separate processes, identical
results checked every round:

| Workload | base | new | new / base, median (IQR) |
|---|---|---|---|
| one move, no `empty` transition | 205 ns | 107 ns | 0.52 |
| one move, two property-layer `empty` transitions | 315 ns | 200 ns | 0.63 |
| one move to a random neighbour (`cell.neighborhood.select_random_cell()`) | 677 ns | 450 to 550 ns | 0.66 to 0.81 |
| `grid_epidemic`, `modelly-cells`, small, 20 rounds | 0.121 s | 0.102 s | 0.86 (0.79 to 0.96) |
| `predator_prey`, `modelly-cells`, small, 20 rounds | 0.212 s | 0.185 s | 0.89 (0.83 to 0.95) |
| `grid_epidemic`, `modelly-cells`, large, 10 rounds | 2.62 s | 2.39 s | 0.91 (0.91 to 0.96) |
| `predator_prey`, `modelly-cells`, large, 10 rounds | 2.11 s | 1.96 s | 0.93 (0.89 to 0.95) |

At the large size the gain is 7 to 9%: the rest of a step (the neighbourhood lookup, the
random draw, the column writes, the property-layer `empty` setter) is unchanged.

### Compiled `select` and `agg`

A fourth module, `modelly/_native/fastset.c`, runs the loops behind `AgentSet.select`, `get`
and `agg`, and the two loops every weak `AgentSet` view is made of. Each function ports one
function of `modelly/_native/sets.py`, which is the reference and the fallback, and
`tests/native/test_sets.py` runs the pairs side by side (order, calls, exceptions, dotted
attribute names, dead references, reference counts):

| Function | Python twin | Used by |
|---|---|---|
| `keep_type` | `[a for a in agents if isinstance(a, agent_type)]` | `select(agent_type=...)` |
| `keep_if` | `[a for a in agents if filter_func(a)]` | `select(filter_func)` |
| `attr_values` | `list(map(operator.attrgetter(name), agents))` | `get(name)`, `agg` |
| `live_agents` | `[a for r in list(refs) if (a := r()) is not None]` | `AgentSet.to_list` and everything built on it |
| `make_refs` | `dict.fromkeys([weakref.ref(a, callback) for a in agents])` | every view `select`, `shuffle`, `sort` and `groupby` return |

Paired micro-benchmark, 20,000 agents, compiled and Python alternating in one process for
41 rounds, `time.thread_time`, one pinned core (`nice taskset -c 3`) of a shared 16-core laptop
at load 2 to 6, Python 3.15:

| Function | Python | compiled | compiled / Python, median (IQR) |
|---|---|---|---|
| `keep_type` | 0.274 ms | 0.148 ms | 0.54 (0.53 to 0.55) |
| `keep_if` (a Python lambda) | 0.555 ms | 0.524 ms | 0.95 (0.93 to 0.97) |
| `attr_values` | 0.251 ms | 0.220 ms | 0.89 (0.87 to 0.91) |
| `live_agents` | 0.402 ms | 0.181 ms | 0.45 (0.44 to 0.46) |
| `make_refs` | 1.353 ms | 0.929 ms | 0.69 (0.65 to 0.72) |

`keep_if` gains least: the cost is the call of the filter, and Python 3.15 calls a Python
function from its own bytecode about as cheaply as C can. The playbooks barely use `select`
or `agg` (they are written with column phases), so they show no change: every Modelly variant,
size `large`, `main` and this branch alternating in fresh pinned interpreters for 6 rounds,
had a median ratio between 0.89 and 1.02 with every interquartile range containing 1.0, and
the same results bit for bit on three seeds, compiled and pure.

### Compiled event heap

Every scheduled event (and every step, which is an event of the default schedule) went
through `heapq` on `Event` objects, so each push and pop called `Event.__lt__`, a Python
method, about log2(n) times. A fifth module, `modelly/_native/fastevents.c`, holds the
event list's heap: `EventHeap` runs `heapq`'s own sift steps, in the same order, on entries
that carry the event's time, priority and unique id, read once when it is pushed and compared
as C numbers. That gives exactly what `Event.__lt__` gives for an `Event` whose time is a
float, a numpy `float64` or an int of magnitude at most 2^53 (all exact as doubles); a
subclass of `Event`, a `Fraction` time or a larger int is compared by calling `<` on the
events, as `heapq` does. The twin, `PyEventHeap` in `modelly/_native/events.py`, is the
previous list with `heapq`; `tests/native/test_event_heap.py` runs both on random schedules
(ties, numpy times, huge ints, fractions, NaN, subclasses, cancellations, compactions) and
checks every pop and the whole heap array after every operation. Both pickle through
`EventList` as the events in heap order, the format of 1.3, so a checkpoint written with the
compiled heap resumes under `MODELLY_PURE_PYTHON=1` and the reverse
(`tests/native/test_event_heap_pickle.py`, wolf-sheep resumed bit for bit). The keys are read
at push: an event's time and priority must not change while it is on a list, which they never
could without breaking the heap.

Two changes around it, both in Python and both in the twin too: time advance asks the heap for
the next event *if it is due* (`pop_due`) instead of popping the first future event and pushing
it back, and `schedule_event` builds one weak reference to the callback instead of two (a
`WeakMethod` costs about 0.5 µs); the event still refuses a callback that dies with the call.

Measured locally against the 1.3.3 release (built from its tag with the same compiler and
dependencies), both sides in that environment's interpreter, CPU time in fresh interpreters,
the two alternating, pinned with `taskset -c 3` on a shared 16-core laptop, every round's
results hashed and compared (identical in every round):

| Workload | rounds | 1.3.3 | 1.4 | 1.4 / 1.3.3, median (IQR; range) |
|---|---|---|---|---|
| Wolf-sheep (`modelly/examples/advanced/wolf_sheep`, 100x100, 1,000 sheep, 500 wolves, regrowth 10, 40 steps) | 15 | 0.409 s | 0.389 s | 0.95 (0.93 to 0.96; 0.90 to 0.99) |
| 4,000 patches, 600 regrowth events a step, 60 steps | 15 | 0.129 s | 0.091 s | 0.70 (0.69 to 0.71; 0.68 to 0.71) |
| wolf-sheep, both pure Python (`MODELLY_PURE_PYTHON=1`) | 9 | 0.461 s | 0.449 s | 0.97 (0.95 to 0.99; 0.90 to 1.01) |
| the 4,000 patches, both pure Python | 9 | 0.130 s | 0.115 s | 0.89 (0.88 to 0.89; 0.87 to 0.90) |

Wolf-sheep schedules one regrowth event per patch eaten (several hundred a step); the rest of
its step is the agents' own Python, so the event list is a small share of it and the gain is
5%: measurable (every one of 15 rounds faster), not large. The
predator-prey playbook regrows its grass as a column and schedules no event but the step, so
it has nothing for the heap to speed up (see the release comparison below).

### Compiled column gather

A `DataCollector` attribute reporter, `AgentSet.get` and `agg` read one attribute per agent
through `operator.attrgetter`. For a `Column` attribute that calls its Python getter from C,
a frame per agent, unless the collected agents are exactly one class's whole table (then the
column is sliced). `fastset.attr_values` now runs the getter's three reads itself,
`agent._column_table._views[position][agent._column_row]`, for any agent whose class's
attribute is a Column property (the getter carries its position), caching each class's position
(revalidated on the class's version tag) and its table's view; any error runs the getter, which
raises what it raises (`ColumnMissingError` for a removed agent). Plain attributes are read as
before. The collector uses it one attribute at a time, mixed reporter sets included; the rows
are identical (`tests/native/test_column_gather.py`, every dtype, interleaved classes,
overridden and replaced properties, grown tables).

| Workload (paired as above) | rounds | 1.3.3 | 1.4 | 1.4 / 1.3.3, median (IQR; range) |
|---|---|---|---|---|
| `collect`, 20,000 agents of two Column classes interleaved, two attribute reporters, 40 collections | 15 | 0.239 s | 0.112 s | 0.47 (0.46 to 0.47; 0.44 to 0.48) |
| the same, both pure Python | 9 | 0.239 s | 0.239 s | 1.00 (0.99 to 1.01; 0.96 to 1.01) |
| `attr_values` alone, per agent, Python twin (1.3's code) against compiled, in one process, Column / plain attribute | 3 | 95 to 102 ns / 18 ns | 38 to 41 ns / 16 ns | 0.40 / 0.88 |

### Profile-guided optimisation

`benchmarks/pgo.py` builds the compiled modules twice from the same source: once with the
build's flags (-O3), once with GCC 16's profile-guided optimisation (-fprofile-generate, a
training run of every Modelly playbook at size small, the 17 core operations and an
event-heavy schedule, `benchmarks/pgo_training.py`, then -fprofile-use), and times every
Modelly playbook variant at size large in the two, paired as `modelly bench --against` does
(7 rounds, pinned to core 3, results identical in every round, measured locally). The
medians fall on both sides of 1 (0.993 to 1.003) and the interquartile ranges are within
1.5% of it, two of them entirely below 1 by at most 0.7% and one entirely above it by at most
0.5%: no playbook is measurably faster. What the compiled modules do per call
is a handful of C operations around interpreter calls, and the branches a profile could
reorder are already the predictable ones. The build does not use a profile, and
`hatch_build.py` has no PGO option. Clang (which needs `llvm-profdata merge` between the two
steps) and MSVC (`/GL` with `/LTCG:PGINSTRUMENT` and `/LTCG:PGOPTIMIZE`) were not tried: this
machine has no MSVC, and the measurement above gives no reason to expect a different answer.

| Variant (large) | -O3 | PGO | PGO / -O3, median (IQR) |
|---|---|---|---|
| grid_epidemic / modelly-cells | 1.252 s | 1.211 s | 1.002 (0.974 to 1.036) |
| grid_epidemic / modelly | 0.135 s | 0.135 s | 1.000 (0.995 to 1.004) |
| predator_prey / modelly-cells | 0.937 s | 0.934 s | 0.997 (0.992 to 1.003) |
| predator_prey / modelly | 0.273 s | 0.272 s | 1.003 (0.993 to 1.007) |
| flocking / modelly | 0.313 s | 0.311 s | 0.998 (0.995 to 1.004) |
| network_contagion / modelly | 0.332 s | 0.330 s | 0.996 (0.985 to 0.999) |
| insect_cohorts / modelly | 0.278 s | 0.280 s | 1.000 (0.984 to 1.008) |
| insect_cohorts / modelly-cohorts | 0.007 s | 0.007 s | 1.000 (0.986 to 1.013) |
| schelling / modelly-cells | 0.242 s | 0.243 s | 0.998 (0.991 to 1.017) |
| schelling / modelly | 0.218 s | 0.219 s | 1.001 (0.999 to 1.005) |
| boltzmann_wealth / modelly | 0.150 s | 0.149 s | 0.995 (0.989 to 1.008) |
| sugarscape / modelly-cells | 0.461 s | 0.459 s | 0.993 (0.991 to 0.998) |
| sugarscape / modelly | 0.152 s | 0.153 s | 1.003 (1.001 to 1.005) |

An earlier, busier session (the same build, 7 rounds) gave medians from 0.94 to 1.08, every
interquartile range containing 1.

### 1.4 against 1.3.3, playbook by playbook

`modelly bench --against 1.3.3 --size large --rounds 9 --core 3`, measured locally: every
Modelly variant, this checkout and 1.3.3 built from its tag with the same compiler and
dependencies, both in the 1.3.3 environment's interpreter, the sides alternating in fresh
interpreters, results identical in every round, the machine otherwise quiet (load 1 to 2).
Ratio is 1.4 / 1.3.3, below 1 is faster:

| Variant (large) | 1.3.3 | 1.4 | ratio, median (IQR) |
|---|---|---|---|
| grid_epidemic / modelly-cells | 1.201 s | 1.196 s | 0.988 (0.984 to 1.009) |
| grid_epidemic / modelly | 0.130 s | 0.131 s | 1.001 (0.996 to 1.004) |
| predator_prey / modelly-cells | 0.926 s | 0.941 s | 0.998 (0.978 to 1.016) |
| predator_prey / modelly | 0.270 s | 0.270 s | 1.003 (0.999 to 1.011) |
| flocking / modelly | 0.310 s | 0.310 s | 0.999 (0.998 to 1.006) |
| network_contagion / modelly | 0.325 s | 0.325 s | 1.002 (0.999 to 1.008) |
| insect_cohorts / modelly | 0.277 s | 0.277 s | 0.998 (0.995 to 1.009) |
| insect_cohorts / modelly-cohorts | 0.007 s | 0.007 s | 0.986 (0.972 to 1.000) |
| schelling / modelly-cells | 0.240 s | 0.238 s | 0.997 (0.988 to 1.005) |
| schelling / modelly | 0.216 s | 0.216 s | 1.003 (0.994 to 1.010) |
| boltzmann_wealth / modelly | 0.150 s | 0.148 s | 0.990 (0.984 to 0.996) |
| sugarscape / modelly-cells | 0.463 s | 0.463 s | 0.999 (0.993 to 1.003) |
| sugarscape / modelly | 0.152 s | 0.152 s | 1.004 (1.001 to 1.008) |

No variant is slower by the guard's criterion; the largest median, Sugarscape's 1.004, has its
whole interquartile range within 1%. The playbooks are written with column phases and
schedule no event but the step, so the event heap and the column gather have nothing to
speed up in them; predator-prey in particular regrows its grass as a column, so it is not
faster (the event-heavy wolf-sheep example above is). An earlier session that ran the
checkout in a development interpreter with pyarrow installed measured the grid epidemic 2 to
4% slower; split into build and run, the difference was all in the run's garbage collection,
and with both sides in one interpreter it is 0.99 (20 rounds, IQR 0.96 to 1.03). That is why
`--against` now runs both sides in the release environment's interpreter.

The performance guard (`python -m modelly.dev perf`, 17 core operations, measured locally)
finds no operation slower than 1.3.3: medians from 0.983 (creating and removing agents with
columns) to 1.028 (creating and removing plain agents, IQR 0.994 to 1.034); the two
neighbourhood walks read 1.016 and 1.019 with lower quartiles of 1.002 and 1.004, under the
guard's 3% threshold and on code this release does not change; `schedule+run event` reads
0.993, since its 500 events at distinct times make every heap comparison a single step.

Measured on Linux only: Windows and macOS could not be measured on this machine, so the
claim "no playbook slower than 1.3.3" holds for Linux x86-64 and is untested elsewhere.

### Memory-mapped columns

`modelly.core.storage` decides where a table's columns live. `InMemory` is the default and
what 1.3 did. `MemoryMapped(directory)` keeps every numeric column in a `numpy.memmap` file
in a fresh folder under `directory`; the operating system pages rows in and out, so a table
can hold more rows than fit in memory, and a column that doubles is grown by extending its
file, without copying the rows already written. Opt in with `model.columns.storage =
MemoryMapped(...)` before the first agent of a class is created, or
`CohortTable(rng, storage=MemoryMapped(...), ...)`. The folder is deleted by `close()`, at the
end of a `with` block, or when the storage is garbage-collected. Object columns cannot be
mapped and stay in memory. A checkpoint (or any pickle) carries the rows, not the file names,
and loading it copies them into a new folder under the same directory; since a checkpoint is
built in memory, saving and loading one needs as much memory as its columns.
`tests/core/test_storage.py` checks that a memory-mapped run holds the same rows as an
in-memory one (agents growing past several doublings, and a cohort table of three million
rows on disk), that checkpoints resume bit for bit in a new folder, and that the folder goes.

A row of a `ColumnTable` belongs to an `Agent` object, which stays in memory (225 bytes with
its registry entries, "Memory per agent" below, before its row attributes), so a hundred
million agents need over 22 GB for the objects alone, whatever the columns' storage. A hundred million rows do fit as
a `CohortTable`, rows without objects. `benchmarks/large_columns.py` builds one (count, stage,
age, patch and a float trait per row, 19 bytes) and runs a stage-structured life cycle on it:
binomial thinning by stage, ageing, stage transitions and offspring draws.

The run, measured locally: 100 million rows (2.55 GB of columns at the table's capacity of
2^27 rows), three steps, each in its own systemd scope with a hard limit and no swap
(`systemd-run --user --scope -p MemoryMax=... -p MemorySwapMax=0`); "cgroup peak" is the
scope's `memory.peak`, which counts the mapped file pages it holds as well as anonymous
memory. Results identical across the runs that finished (3,815,571,746 individuals, the same
offspring count).

| Storage | MemoryMax | finished | build | seconds per step | cgroup peak |
|---|---|---|---|---|---|
| memory-mapped | 16 GB | yes | 2.2 s | 10.4, 9.5, 9.3 | 3.61 GB |
| in memory | 16 GB | yes | 3.1 s | 8.7, 8.4, 8.3 | 4.26 GB |
| memory-mapped | 3 GB | yes | 2.7 s | 10.1, 9.6, 11.6 | 3.22 GB (the limit: file pages were reclaimed) |
| in memory | 3 GB | no: killed by the limit | | | |

A hundred million rows run well inside 16 GB either way; the file-backed table costs 10 to
15% per step here (the page cache sat on a fast SSD and the whole file fit in memory). Under a
limit smaller than the run needs in memory, the memory-mapped table finishes and the
in-memory one is killed. The temporaries of a step (a 100-million-element survival array and
the binomial draws, 800 MB each) stay in memory whatever the storage. A table whose columns
exceed the machine's memory follows the same path, at the disk's speed.

### Free-threaded CPython

All four modules load on free-threaded CPython (wheels for 3.14t and 3.15t; tested on 3.15t)
and declare `Py_MOD_GIL_NOT_USED`, so importing Modelly leaves the GIL off; before 1.3 they
refused to load and the pure twins ran instead. What each one does to be safe:

- `fastrng`: every draw holds the generator's per-object critical section, the lock
  `_random.Random`'s own methods take, so a draw from C and a `random()` from the standard
  library never interleave on one state. A list being shuffled, sampled or chosen from is
  locked with it. Draws from one generator shared by threads are atomic (tested: the threads
  together draw exactly the serial sequence, in some order), but which thread gets which number
  depends on scheduling: give each thread its own model, or its own generator.
- `fastloop`: list items are read as new references; a cell's `connections` dict is walked
  inside its critical section.
- `fastcell`: the per-type layout cache is per thread; `bind()` and its readers share one
  `PyMutex`; slots are read through `getattr` and `list.remove` runs itself, since both take
  the object's lock.
- `fastset`: list items are read as new references; weak-reference keys are snapshotted with
  `PyDict_Keys`, which locks the dict.

GIL builds compile the same code with the locks as empty blocks (`modelly/_native/ftcompat.h`);
paired micro-benchmarks of `shuffle`, `randint`, `choice`, `sample`, the cell move, `do` and the
neighbourhood walk against `main` were within noise (medians 0.92 to 0.98). On CPython 3.15t
(Linux x86-64) the whole suite passes with the compiled modules, and
`tests/native/test_threads.py` (four threads; shared draws, independent replicates on threads
equal to serial runs, agents moved across a shared grid, `select` and `agg` while another
thread adds and removes agents) passed 25 repeated runs at ten times its default rounds.
ThreadSanitizer was not run: it needs an instrumented interpreter.

`fastevents` (1.4) holds the heap's critical section in every method and declares
`Py_MOD_GIL_NOT_USED`; the column gather in `fastset` reads items as new references and type
version tags with relaxed loads. Both were built and tested on the GIL interpreter only: the
machine they were written on has no free-threaded CPython, so the 3.15t build of these two is
untested.

### Memory per agent

Measured with `tracemalloc` on Python 3.15 (Linux x86-64), after `gc.collect()`, as the bytes
traced while 100,000 agents are created, minus the list that holds them. This is the
framework's own share; an agent's model attributes come on top.

| What | Bytes per agent | Where it goes |
|---|---|---|
| `Agent(model)` | 225 | the object with its inline attribute values (88), `unique_id` (an int above 256, 32), and one entry in each of the two registries (`model.agents` and the per-type set, about 50 each at this size including the dicts' spare room) |
| `CellAgent` placed in a cell | 265 | the above, the `_modelly_cell` attribute and the entry in the cell's agent list |
| an entry of a weak `AgentSet` view | 132 | a `weakref.ref` with its callback and the dict entry; only while the view lives |

Per playbook, `large`, bytes traced by the whole model divided by its population, after
building and after the run (the grid, the property layers, the columns and the data collector
dominate; this is the baseline the 1.3 memory work is measured against):

| Playbook / variant | agents built | bytes per agent, built | population at the end | bytes per agent, end |
|---|---|---|---|---|
| `grid_epidemic` / `modelly-cells` | 20,000 | 1,704 | 20,000 | 3,103 |
| `grid_epidemic` / `modelly` | 20,000 | 1,656 | 20,000 | 2,232 |
| `predator_prey` / `modelly-cells` | 1,600 | 21,360 | 5,455 | 12,876 |
| `predator_prey` / `modelly` | 1,600 | 21,320 | 5,343 | 8,948 |
| `flocking` / `modelly` | 4,000 | 314 | 4,000 | 4,179 |
| `network_contagion` / `modelly` | 30,000 | 2,542 | 30,000 | 2,595 |
| `insect_cohorts` / `modelly` | 500 | 253 | 26,466 | 413 |
| `insect_cohorts` / `modelly-cohorts` | 0 (cohort rows) | - | 26,660 | 2 |
| `schelling` / `modelly-cells` | 32,022 | 1,388 | 32,022 | 1,792 |
| `schelling` / `modelly` | 32,022 | 1,332 | 32,022 | 1,708 |
| `boltzmann_wealth` / `modelly` | 10,000 | 265 | 10,000 | 11,190 |
| `sugarscape` / `modelly-cells` | 1,600 | 4,587 | 714 | 47,405 |
| `sugarscape` / `modelly` | 1,600 | 9,514 | 713 | 21,127 |

No reduction was kept in 1.3 so far. `__slots__` for the framework attributes (`model`,
`unique_id`) was measured and gives nothing on Python 3.13 and later: an instance without
slots already stores its attributes inline at 8 bytes each, exactly what a slot costs (88 bytes
for a two-attribute object either way, 112 with three more attributes in a subclass), while it
would forbid a subclass from relying on `Agent.__dict__` semantics. The two registry entries
are the next target; a more compact registry must keep iteration order, membership in C and
the removal semantics, so it is a design change rather than a patch.

### No regression from release to release

Every release is benchmarked against the previous published one before it is tagged: the
previous wheel from PyPI against the new wheel built by the release workflow (same
toolchain), installed with identical dependencies, on one machine. Three measurements, each
in paired, alternating runs so that load and frequency drift hit both versions alike:

- **Core operations** (17, including Column reads, agent removal with columns, cell moves
  and neighbourhood walks): two persistent processes pinned to one core, short bursts in
  ABBA order, over several sessions with the starting version swapped; a numpy-only control
  must read 1.00.
- **The playbooks** (13 Modelly variants): the same seeds in two persistent processes, ABBA,
  CPU time of the steps, results compared seed by seed.
- **A research notebook** (a 576-season factorial at 1/30 scale): its seasons in chunks
  alternating between the two versions, records compared chunk by chunk.

1.3.1 against 1.2.0 (median ratio of CPU time, 1.3.1 / 1.2.0; below 1 is faster):

| Measurement | Ratio | Results |
|---|---|---|
| `AgentSet.select` | 0.79 | |
| `AgentSet.agg` | 0.88 | |
| Creating and removing agents | 0.94 | |
| `shuffle_do` | 0.97 | |
| `do`, Column read and write, cell moves, neighbourhood walks, data collection, events, random draws | 0.98 to 1.01, within noise | |
| Playbooks: insect cohorts (individuals) | 0.94 | identical |
| Playbooks: the other twelve variants | 0.98 to 1.00 | identical |
| TIS notebook at 1/30, 576 seasons | 1.00 (17.92 s and 17.92 s) | identical |

1.3.2 against 1.3.1 (its only change to the library is the ABC-SMC correction): both built
from their git tags with the same compiler and dependencies.

| Measurement | Ratio, 1.3.2 / 1.3.1 | Results |
|---|---|---|
| Core operations (pre-commit guard, 17 timings) | 0.94 to 1.03, none slower by the guard's criterion | |
| Playbooks, 13 Modelly variants, 5 rounds | 0.96 to 1.04 (median of the per-round ratios) | identical |
| The three noisiest re-timed with 15 rounds | 0.99, 1.01, 1.07 (lower quartiles 0.97, 0.98, 0.99) | identical |
| TIS notebook at 1/30, 7 alternating rounds | 0.98 (paired median) | identical |

The playbooks and the timed operations import no module that changed: the compiled modules'
machine code is identical to 1.3.1's (`objdump -d`), so the remaining spread is the
machine's noise.

1.3.3 against 1.3.2 (its only change is to the codemod, `modelly.migrate`): both built from
their git tags with the same compiler and dependencies, timed with the performance governor
and turbo off.

| Measurement | Ratio, 1.3.3 / 1.3.2 | Results |
|---|---|---|
| Core operations (pre-commit guard, 17 timings) | 0.83 to 1.02 by median, none slower by the guard's criterion (cell move: median 1.14, lower quartile 0.93) | |
| Playbooks, 13 Modelly variants, 5 rounds | 0.99 to 1.02 (median of the per-round ratios) | identical |
| TIS notebook at 1/30, 5 alternating rounds | 1.00 (paired median; per round 0.88 to 1.02) | identical |

The tutorials and benchmark notebooks (17) run against the 1.3.3 wheel.

Between releases, a pre-commit hook (`python -m modelly.dev install-hooks`) refuses any
commit that makes one of 17 core operations more than 3% slower than the last release, in
about ten seconds; CONTRIBUTING.md describes it.

1.3.0 had two small regressions that this check found after its release: a Column read
was about 2.5% slower (the getter kept the column's name for a clearer error) and, on
regular builds, the neighbourhood walk and the cell move paid for free-threading safety
they do not need. 1.3.1 removes both; the free-threaded builds keep their safe paths.

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

**Stage two: the framework.** Whole-cell rounds swing by up to 2x on a shared machine, so
the comparison moved to a finer instrument: two persistent processes, one per framework,
pinned to the same core, running the 576 seasons in 48 chunks with the order alternating,
each chunk's records hashed and compared (no mismatch in any run). Measured that way, the
gap before this round was 2.1%, and none of it was in the model's arithmetic:

1. **The random draws.** `FastRandom.randint` had become 4% *slower* than the standard
   library on CPython 3.15, which now inlines Python-to-Python calls well; the `operator.index`
   calls were the difference. The table above lists the fixes; this was the largest item.
2. **Agent birth and death.** One model flag (`_quiet`: default registry and nobody
   listening) replaces four attribute reads, and one class flag (`_extra_hooks`: columns or
   datasets) replaces two. The flag only ever turns false (on `observe`, `observe_class`, a
   batch, a suppress, or an overridden `register_agent`), so a stale value can only send an
   agent down the slower, still correct path. Creation went from 295 ns to 225 ns at the
   notebook's live population, against 281 ns for Mesa.
3. **The garbage collector.** About 11% of the run on both frameworks. Collecting identical
   garbage costs the same on both (78 to 83 ms per 240,000 objects); what differs is where
   collections fall relative to season boundaries, which depends on allocation counts. With
   the collection threshold set equally on both sides, Modelly is ahead at four of five
   values and behind at one. We report the default threshold. `gc.freeze()` after the imports
   would have given Modelly another 2.4%; applied to both sides it gives nothing, so it is a
   process setting rather than an engine property, and Modelly does not do it.

Result at the default settings, experiment cell, separate processes, pinned, alternating
(same output CSV in every round):

| Round | Mesa 2.3 | Modelly | Modelly faster by |
|---|---|---|---|
| 1 | 13.09 s | 12.70 s | 3.0% |
| 2 | 12.71 s | 12.53 s | 1.4% |
| 3 | 12.66 s | 12.50 s | 1.3% |
| 4 | 12.98 s | 12.49 s | 3.8% |

The paired instrument agrees (Modelly/Mesa 0.985 to 0.994 total; 0.969 to 0.983 outside the
collector). The win depends on Modelly's generator: with the port's seeding line left as
`random.Random(seed)`, the same instrument puts Modelly 1.5 to 2% behind, mostly collector
timing. Using `FastRandom` there is fair in the sense this page uses: it is `model.random`'s
own type, and it reproduces the identical stream, so every output is bit-identical.

**Correction (2026-10-25).** An earlier version of this page reported Modelly 12% ahead
(0.877 to 0.884 of Mesa's time). That pairing ran the reference notebook against the
*optimised* Modelly notebook, whose model code had changes the Mesa notebook did not (the
incremental rot score among them), so the ratio mixed the framework with the model
optimisations. Re-measured with the plain codemod port (`port_to_modelly.py`: framework API
only, every line of model logic unchanged) against the unmodified Mesa notebook, at 1/30 scale,
48 chunks per run, same records in every chunk:

| Paired run | Port seeded with | Mesa 2.3 | Modelly | Modelly / Mesa | median chunk |
|---|---|---|---|---|---|
| 1 | `FastRandom` | 27.17 s | 27.62 s | 1.017 (machine shared with other jobs) | 0.895 |
| 2 | `FastRandom` | 23.37 s | 21.86 s | 0.936 | 0.893 |
| 3 | `FastRandom` | 23.60 s | 22.16 s | 0.939 | 0.890 |
| 1 | `random.Random` | 25.00 s | 25.96 s | 1.038 | 1.037 |
| 2 | `random.Random` | 23.36 s | 23.81 s | 1.019 | 1.017 |
| 3 | `random.Random` | 23.71 s | 24.14 s | 1.018 | 1.009 |

A model written agent by agent runs at Mesa's speed: 6% faster with the compiled generator,
about 2% slower with the standard library's.

Models that spend most of their time in framework calls gain more from the same treatment.
Two public playbooks without a Mesa 2 grid, ported from Mesa 2.3 by the codemod and the steps
it reports (`benchmarks/ports/`), run at 0.22 (insects) and 0.37 (Boltzmann wealth) of Mesa
2.3's CPU time, bit-identical. Five playbooks ported from their Mesa 3.5 versions by the codemod
alone (`benchmarks/ports_mesa3/`) run at 0.45 (Boltzmann wealth), 0.51 (insects), 0.74 (grid
epidemic), 0.86 (network) and 0.93 (Schelling) of Mesa 3.5's CPU time. They are not
bit-identical, since Modelly derives `model.random` from the seed differently, but over 100
seeds 24 of their 26 statistics are equivalent within half a standard deviation and no test is
significant after a Holm correction. Flocking (Mesa's legacy `ContinuousSpace`) and
predator-prey and Sugarscape (Mesa 3.5's `PropertyLayer`) do not port by the codemod alone.
Timings and agreement: `paper/data/port_public.json`, ten alternating rounds, pinned.

Measured and rejected on this workload: a `shuffle` that draws its random words in one call
(it reproduces the permutation but leaves the stream in a different place for the next draw,
and is 3x slower); a cheaper `Model` construction (it is 18 µs; 576 of them are 10 ms).

### The playbooks: same model, each framework's own idiom

The port above answers "what does identical code cost". The second question is what each
framework lets a modeller write. `benchmarks/playbooks/` holds eight models, each implemented
for Mesa 2.3 with per-agent methods on `MultiGrid`, `SingleGrid`, `ContinuousSpace` and
`NetworkGrid`, for the current Mesa 3.5 with its cell spaces (`OrthogonalMooreGrid`,
`CellAgent`, `Network`), its experimental continuous space and `AgentSet.shuffle_do`, as in
Mesa's own examples, and for Modelly with `Column` state, `CellIndex` (integer rows for the cells of
any discrete space plus their sparse adjacency), `Occupancy` / `claim`, `pairs_within` /
`move_all`, `ColumnTable.thin` and the `DataCollector` column reporters. The rules for a fair comparison, enforced by the runner:

1. Same model: same rules, same phase order (synchronous, or one agent at a time in a random
   order), same parameters, same graph and initial positions where seeds can be shared; the
   Mesa side uses numpy where a Mesa modeller would.
2. Agreement in distribution, checked: every implementation runs the same seeds and each
   summary statistic is compared with the Mesa reference by Welch's t-test (flagged below
   0.01). The implementations draw their random numbers in different orders, so the outputs
   differ run by run and must agree in law; `vectorised_phases.md` states why each vectorised
   phase has the law of its per-agent loop.
3. Determinism, checked: the first seed runs twice per implementation. (This check caught the
   Mesa side being unseeded when the seed was passed positionally: Mesa 2.3 reads it from the
   keyword arguments in `Model.__new__`.)
4. CPU time of a fresh interpreter per run, build and steps timed separately, pinned to one
   core, implementations alternating over ten rounds, every round reported.

The Mesa 3.5 implementations agree with Mesa 2.3's: over 100 paired seeds all 40 summary
statistics are equivalent within half a standard deviation, and no test falls below 5%
(`paper/data/agreement_small_baselines_summary.json`, which also holds the mesa-frames
variants); flocking, the network and the insects draw the
same numbers in the same order and reproduce Mesa 2.3 run for run. Where a phase searches cells
one agent at a time (Sugarscape's foragers), every implementation uses the same single-pass
loop. Median CPU seconds of the steps at the large size, all variants in one session, ten
rounds, pinned to a performance core (CPU 2, performance governor, turbo disabled, so the core runs at its fixed 1.9 GHz base
frequency; every per-round ratio is within 15% of its median). Absolute seconds are longer than
with turbo; the ratios are the point. "Mesa 3.5 + numpy" (`mesa3np_model.py`, three playbooks) is the
hand-vectorised Mesa baseline: a `mesa.Model` that holds the population as numpy arrays over
Mesa's grid and property layers, with no `Agent` objects:

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

The "cell lists" column is the same model with Mesa's data structure, every cell holding the
list of its agents, so movement and predation stay per-agent loops: 1.5 to 2.5x over Mesa
2.3 on the epidemic and predator-prey (1.3 to 14x over Mesa 2.3 and 1.3 to 11x over Mesa 3.5
across its four playbooks). The gap opens when the cell becomes a column of rows: the random walk is one
`random_neighbor` call over the grid's CSR adjacency, the exposure count a `bincount`, the
predation a vectorised matching with the law of the shuffled sequential rule. Construction is
reported separately (a 180x180 Moore grid builds in 0.11 s, a 30,000-node network in 0.4 s,
against milliseconds for Mesa 2.3's lazy structures, and about the same for Mesa 3.5's cell
spaces); the build+run speed-ups over Mesa 2.3 in the results are correspondingly lower (22x,
5.2x, 32x, 10x, 5.4x, 217x, 9.3x, 5.9x, 4.0x). Mesa 3.5 is itself faster than Mesa 2.3 on five
playbooks (1.3x to 3.1x), about as fast on Sugarscape (1.02x) and flocking (1.00x; both use `mesa.space.ContinuousSpace`,
which runs it 1.6x faster than Mesa 3.5's experimental continuous space) and slower on
predator-prey (0.91x). mesa-frames (development branch, commit `ef92326`, polars 2.0 on one
thread) is 2.1x to 6.5x faster than Mesa 2.3 on three of its four playbooks and slower on
Sugarscape (0.71x); Modelly columns are 3.0x to 9.4x faster than mesa-frames. One thread is
mesa-frames' better setting here: with all of polars' threads it is slower on three of the four
workloads (grid epidemic 1.73 s against 1.52 s, Boltzmann wealth 2.61 s against 1.46 s,
Sugarscape 4.29 s against 2.96 s) and faster only on Schelling (2.12 s against 2.90 s;
`paper/data/frames_threads.json`).

The hand-vectorised Mesa 3.5 baseline is faster than Modelly's columns: 4.4x on the epidemic,
1.8x on Schelling, 2.8x on Boltzmann wealth. It is the same arithmetic without the agents:
Modelly keeps an `Agent` per individual, with its identity, its `step()` and the agent-set API,
and that bookkeeping is the difference. It agrees with Mesa 2.3 in distribution
(`paper/data/agreement_small_mesa3np_summary.json`; one statistic, Schelling's segregation
index, differs by 0.24 sd, p = 0.045 after Holm).

The last three playbooks have phases that are sequential by nature, and each still has an
exact array form (`vectorised_phases.md`, §7 to §9). Schelling's unhappy residents move one at
a time to random empty cells; since every move takes one empty cell and frees one, the pool of
empty cells keeps its size, and all the moves become one sort over slots drawn up front. In the
Boltzmann exchange, who gives in the random order is the least fixed point of a monotone map
over the drawn order and partners, reached in a few array passes; the `DataCollector` slices
the wealth column instead of visiting agents. In Sugarscape the foragers' choices depend on the
cells taken before their turn, so the walk to the first free cell stays a loop, but everything
it reads (the visible cells, their sugar, the head of each forager's ranking) is one array
pass, and eating and starving move after the loop without changing the law. Rankings are not
sorted up front: the loop takes a forager's head when it is free and sorts the ranking only
when that cell is not free at its turn (under a third of the turns). That gives the same runs,
bit for bit, as sorting every ranking, and is 2.5x faster (median of 5 paired runs, range 1.9
to 2.6x, thread CPU time, large size, a loaded machine). Schelling's "cell lists" variant is
far ahead of Mesa 2.3 (14x) because its happiness count, three quarters of Mesa's run, is an
array pass even there; Mesa's move to a random empty cell already runs in constant expected
time. Sugarscape's is not (1.3x): it runs the same single-pass search as both Mesa versions.
(An earlier Mesa 2.3 Sugarscape built a whole-grid mask per forager with `select_cells`; the
cached neighbourhood gives the same runs, bit for bit, 4 to 5x faster, and is what Mesa's own
example does.)

The insect playbook is a stage-structured population under sterile releases, an original
model with the dynamics of the medfly workload (thousands of eggs a day, stage-specific
mortality, density-dependent larval survival). Agent creation is at parity, so the
individual-level gap is the per-agent loop only (5.7x over Mesa 2.3, 3.2x over Mesa 3.5). The cohort variant represents every
insect in the same (stage, age, sex) class as one row and thins it with a binomial draw; it
has the same law as the individual model (the agreement table shows it) and runs in 11 ms.
Absolute times vary by up to 2x between sessions on a shared machine; the ratios much less.

## GPU backend

The `modelly-gpu` variant of the grid epidemic (`benchmarks/playbooks/grid_epidemic/modelly_gpu.py`)
is the column variant `modelly` with its step on CuPy: the same agents and grid, the columns as a
`DeviceTable`, the adjacency as a `DeviceCellIndex`, the draws from a `PhiloxStream`
([GPU arrays](gpu.md)). Measured by `benchmarks/playbooks/gpu_speedup.py` at 10 million agents
on a 1000 x 1000 torus (ten agents per cell; the playbook's density would need 16 million Python
cell objects), 60 steps, seed 1. Raw numbers: `benchmarks/playbooks/results/gpu_speedup.json`.

**Machine.** A laptop: Intel Core Ultra 7 356H, 30 GB, and an NVIDIA GeForce RTX 5050 Laptop
GPU (8 GB, driver 615.78, CUDA runtime 13.2 from the `cupy-cuda13x` 14.2.0 wheel); numpy 2.5.4.
Shared with other jobs: every run was started through a guard that lets one heavy job run at a
time, but the load from lighter work was not controlled and the CPU frequency was not pinned.

**Method.** A fresh interpreter per run, the two variants alternating; the wall clock around the
60 steps with the device synchronised before each reading (a GPU's time is not the process's CPU
time); the build (agents, grid, upload) timed apart. One untimed GPU run first fills CuPy's
kernel cache.

| Steps of the grid epidemic, 10 million agents | CPU column variant `modelly` | `modelly-gpu` on CuPy | speed-up |
|---|---|---|---|
| CPU variant on Python 3.15.1 (Modelly's environment), 3 rounds | 20.65, 21.05, 21.39 s | 0.612, 0.608, 0.622 s | 33.7x, 34.6x, 34.4x (median 34.4x) |
| CPU variant on Python 3.14.8 (the GPU environment's interpreter), 2 rounds | 23.91, 24.48 s | 0.722, 0.725 s | 33.1x, 33.8x |
| Build (agents, grid and, for the GPU, the upload) | 22 to 42 s | 26 to 41 s | none |

About 350 ms per step on one CPU core against 10 ms on the GPU. The building is the same Python
work for both (10 million `Person` agents) and dominates a 60-step run: build plus steps is
1.5 to 1.7x faster on the GPU (Python 3.15 rounds). The 10x target of the 1.4.0 roadmap is met on this mid-range laptop
GPU for the steps; it is not a claim about construction, which the GPU does not touch.

**Equality.** `gpu_speedup.py --equality` ran `modelly-gpu` with the same seed on numpy (69 s:
the numpy fallback computes Philox numbers with array operations) and on CuPy (1.9 s, kernel
compilation included): the infected series of the 60 steps is identical and so is the SHA-256 of
the final `state`, `days` and `row` columns of all 10 million agents. The test suite checks the
same on every backend that loads (`tests/gpu`), JAX with 64-bit types included. Against the CPU
column variant, which draws from `model.rng`, the agreement is in distribution, as for every
playbook variant.

**Where the GPU does not pay.** At the playbook's own large size (20,000 agents) the steps take
0.17 to 0.21 s on CuPy against 0.11 s for the CPU column variant (3 seeds each): kernel launches
and synchronisations cost more than the arithmetic. The insect cohorts on a `DeviceCohortTable`
take 1.9 to 2.1 s for 120 days against 10 ms for the host `CohortTable` (3 seeds): the table has
fewer than two hundred rows. Both variants run on CuPy because the roadmap asks that they do, and
give the numpy run's integers there; neither is a reason to use a GPU. Apple Metal (JAX) was not
measured: no Apple GPU was available.

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
3. **Compiled hot loops.** The neighbourhood lookup and `do` / `shuffle_do` on the model's
   registries now run in `modelly/_native/fastloop.c`, the cell move in
   `modelly/_native/fastcell.c` (7 to 14% on the cell-list playbooks), and `select`, `agg`
   and the weak views in `modelly/_native/fastset.c`. What remains per agent
   is the random-neighbour lookup around the draw and the property-layer `empty` setter.

## How to re-run

```bash
python benchmarks/global_benchmark.py        # the four reference models, saves timings_N.pickle
python benchmarks/compare_timings.py a.pickle b.pickle
python benchmarks/playbooks/compare.py --core 5   # the eight playbooks against Mesa 2.3
```

`modelly bench` runs the Modelly variants of the playbooks on every operating system without
shell tools, keeps a history and reports regressions. Run it from the repository root (or
point `--playbooks` at the directory):

```bash
modelly bench --label v1.2.0                       # record a named baseline (size large, 3 rounds)
modelly bench --baseline v1.2.0                    # compare; exit 1 on a regression above 10%
modelly bench --size small --rounds 5 --only grid_epidemic --only schelling:modelly
modelly bench --history ~/bench/modelly.jsonl --core 3 --threshold 0.05
MESA_PYTHON=.venv-mesa2/bin/python modelly bench   # the Mesa variants too
modelly bench --against 1.3.3 --rounds 7 --core 3  # this checkout against a release, paired
```

`--against VERSION` (or `release`, the last tag) builds that release from its tag in this
repository with the performance guard's builder (same compiler, same numpy, pandas, scipy and
networkx, cached in `.modelly-bench/`), then runs every Modelly variant once per side per
round, the side order swapped every round, with the same seed. Both sides run in the release
environment's interpreter, the checkout's with the checkout first on `PYTHONPATH`, so both
import the same third-party packages: run from a development environment that has pyarrow
installed, the checkout imported it and the release did not, which added about 10,000
objects for the garbage collector and moved where its collections fall (the grid epidemic's
60 steps spend more time collecting than computing). The two runs
must give identical results; the report gives each variant's median per-round CPU ratio and
its interquartile range, and exits 1 when a variant's median is above 1 + `--threshold` and
even its lower quartile is above 1 (the performance guard's criterion), or when results
differ. Nothing goes to the history.

Each variant runs in a fresh interpreter; the order of the variants alternates from one round
to the next. Runs are pinned to one core through `psutil` (`pip install modelly-abm[bench]`)
on Linux and Windows; macOS has no CPU affinity API, and the report says the runs were not
pinned. Every invocation appends one JSON line to the history file
(`.modelly-bench/history.jsonl` by default): the Modelly version, which compiled modules were
active, Python, platform, pinning, and every round's CPU seconds per variant. The baseline is
the entry named by `--baseline` (a `--label`, or an index such as `0` or `-2`), else the latest
entry at the same size.
