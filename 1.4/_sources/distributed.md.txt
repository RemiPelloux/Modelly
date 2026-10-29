# From laptop to cluster

`modelly.distributed` (provisional, new in 1.4) splits one model across processes or machines:
each worker holds the agents of one part of the space, and the workers exchange the agents at
their borders. For the same seed a split run gives the same results as one process, byte for
byte: the same reporter values at every step and, at the end, every agent in the same place
with the same attributes and random streams.

```python
from modelly.distributed import Cluster, partition
from modelly.examples.distributed.grid_epidemic import EpidemicScenario, GridEpidemic

scenario = EpidemicScenario(rng=42, width=200, height=200, people=50_000)

with Cluster(backend="dask", workers=4) as cluster:
    model = cluster.build(GridEpidemic, scenario, partition=partition.grid_blocks(2, 2))
    model.run_for(100)
    cluster.collect().to_parquet("runs/epidemic.parquet")
```

The same model runs in one process as any Modelly model does (`GridEpidemic(scenario)`,
`model.run_for(100)`). Splitting it is a choice of backend and partition, not a rewrite.

## What a model must do to be split

Only models written to a contract can be split. Most of it is what a synchronous model does
anyway; the build and the run refuse, with the reason, the breaches they can see.

1. **Declare the split.** A class attribute `partitionable = Partitionable(space=..., phases=...,
   reporters=...)` names the model attribute that holds the space, the phases of one step and
   the reporters. The model's `step` runs the phases: `self.partitionable.step(self)`.
2. **Use per-agent streams.** `agent_streams = True` on the class, and every draw in a phase from
   the agent's own `self.random` or `self.rng`. A phase that draws from `model.random` or
   `model.rng` (directly, or through a space or cell collection seeded with them, such as
   `cell.neighborhood.select_random_cell()`) is refused at the step it happens.
3. **Phases are synchronous and local.** A phase is one method every agent runs. It reads other
   agents only within its `radius` (Chebyshev cells on a grid, hops on a network, distance in a
   continuous space), writes only the agent running it, and does not depend on the order in
   which agents run or neighbours are listed. The usual pattern is a phase that decides
   `next_state` from the neighbours' `state`, then a phase that copies `next_state` to `state`.
4. **Moves happen in moving phases.** A phase declared with `moves=True` may change the agent's
   cell or position; after it, agents standing on another partition's ground migrate there,
   with their random streams. Moves into cells with a capacity are refused: who gets a free
   cell would depend on the order of the moves.
5. **Agents hold plain data.** Attributes are numbers, strings, arrays, tuples and the like, not
   references to agents, cells or the model (keep a stream key or a coordinate instead). Agent
   classes are defined at module level, so they can be sent to another process.
6. **Every agent has a place in the partitioned space**, and the model schedules no events of
   its own. Agents with `Column` state are not supported yet.
7. **Stream keys do not depend on the partition.** An agent's streams are seeded from the
   model's seed and its `stream_key()`, `unique_id` by default. By default every worker builds
   the whole initial population in the single-process order and keeps its part, so `unique_id`
   is the same everywhere. A model that builds only its own part (below), or creates agents
   during the run, overrides `stream_key()` with a key of its own; the build refuses different
   populations keyed on `unique_id`, and a phase that creates such agents is refused.

The breaches the checks cannot see (reading past the radius, depending on the order of
neighbours, writing to another agent) change the results. `check_independence` finds them: it
runs the model in one process and split, and raises at the first output that differs.

```python
from modelly.distributed import check_independence, partition

check_independence(
    GridEpidemic,
    scenario,
    [partition.grid_blocks(2, 2), partition.grid_blocks(4, 4)],
    steps=20,
)
```

Run it on a small scenario before a long split run.

## A model, in full

The grid epidemic of `modelly.examples.distributed.grid_epidemic`, shortened:

```python
from modelly import Model
from modelly.distributed import Partitionable, Phase, Sum
from modelly.distributed.building import owns
from modelly.space import OrthogonalMooreGrid
from modelly.space.cells.agents import CellAgent

S, I, R = 0, 1, 2


class Person(CellAgent):
    def __init__(self, model, cell, state, key):
        super().__init__(model)
        self.key, self.cell, self.days = key, cell, 0
        self.state = self.next_state = state

    def stream_key(self):
        return self.key  # the index in the creation order, whoever builds the person

    def move(self):
        self.cell = self.random.choice(self.cell.neighborhood.cells)

    def expose(self):  # reads the people in its own cell and the eight around it
        if self.state == S:
            around = [self.cell, *self.cell.neighborhood.cells]
            k = sum(other.state == I for cell in around for other in cell.agents)
            if k and self.random.random() < 1 - (1 - self.model.scenario.beta) ** k:
                self.next_state = I
        elif self.state == I:
            self.days += 1
            if self.days >= self.model.scenario.recovery:
                self.next_state = R

    def advance(self):
        self.state = self.next_state


def infected(model):
    return sum(1 for agent in model.agents if agent.state == I)


class GridEpidemic(Model):
    agent_streams = True
    partitionable = Partitionable(
        space="grid",
        phases=(Phase("move", moves=True), Phase("expose", radius=1), Phase("advance")),
        reporters={"I": Sum(infected)},
    )

    def __init__(self, scenario):
        super().__init__(scenario=scenario)
        s = self.scenario
        self.grid = OrthogonalMooreGrid(
            (s.width, s.height), torus=True, random=self.random
        )
        cells = list(self.grid.all_cells)
        for key, pick in enumerate(self.rng.integers(0, len(cells), s.people).tolist()):
            if owns(self, cells[pick].coordinate):
                Person(self, cells[pick], I if key < s.infected else S, key)

    def step(self):
        self.partitionable.step(self)
```

The model's own generator is used while building (every worker draws the same numbers there);
during a step only the people's streams are.

## Partitions

| Space | Partition | Halo |
|---|---|---|
| A 2-D grid (torus or not; tested on `OrthogonalMooreGrid`) | `partition.grid_blocks(rows, cols)`: rectangles of nearly equal size, the larger first | cells within `radius` (Chebyshev) of the block |
| A `Network` | `partition.graph(parts, imbalance=0.03)`: nodes ordered by breadth-first search from a far node of each component, cut into equal runs, then refined by greedy boundary moves (k-way Fiduccia-Mattheyses) within the imbalance | nodes within `radius` hops |
| A `ContinuousSpace` | `partition.kd(parts)`: recursive bisection of the domain along its longest side at the population quantile (a k-d tree) | agents within `radius` of the box, wrapping on a torus |

Every partitioner is deterministic and pure numpy, so all workers compute the same layout. The
graph partitioner is not METIS: on a 30 by 30 lattice cut in four it cuts about twice the edges
of the best split, and far fewer than a random one. A layout answers `owner`, `owners`, `halo`
and `neighbours` (`GraphLayout.cut()` and `sizes()` measure a graph split).

## What happens in a step

For each phase, in order:

1. if the phase's radius is above zero, each worker sends copies of its agents within the
   radius of a neighbour (ghosts) to that neighbour, which places them in its copy of the space;
2. every worker runs the phase on its own agents; the run checks that the model's generators
   did not move and that no agent keyed on `unique_id` was created;
3. ghosts are removed;
4. after a moving phase, agents now on another partition's ground are sent there with their
   streams and registered, by sender and then in the sender's order.

Then every worker computes its part of each reporter and the parts are reduced. `Sum`, `Min`
and `Max` are exact on integers; a float `Sum` adds the parts with `math.fsum`, but each part
is rounded before, so use integer reporters where byte identity matters.

## Building only your own part

By default each worker builds the whole initial population, then drops the agents of other
partitions: simple, and always correct, but every worker holds the whole population while it
builds. `owns(model, location)` (in `modelly.distributed.building`) lets the model's `__init__`
build only the agents its worker owns, as the example above does: it is always `True` in one
process, so the model builds the same agents there. The agents need stream keys of their own.
`kd` splits cannot answer `owns`, since their boxes come from the built positions. Each worker
still holds the whole space (every cell of the grid, every node of the network).

## Backends

| Backend | Use | How it runs |
|---|---|---|
| `"local"` | tests, debugging, `check_independence` | every partition in this process, one after the other |
| `"mpi"` | clusters, the fastest exchange | one partition per MPI rank; launch the script with `mpirun -n <partitions> python run.py` |
| `"dask"` | a laptop or a Dask cluster, no MPI needed | one Dask actor per partition (a local cluster of one-thread processes, or `address=` / `client=`) |
| `"ray"` | a Ray cluster | one Ray actor per partition; `ray.init` arguments as options |

Under MPI every rank runs the same script, and every `DistributedModel` method is collective: call
it on every rank, never inside `if cluster.is_root:`. All ranks get the same results; write files
from the root only:

```python
with Cluster(backend="mpi") as cluster:  # mpirun -n 4 python run.py
    model = cluster.build(GridEpidemic, scenario, partition.grid_blocks(2, 2))
    model.run_for(365)
    frame = cluster.collect()
    if cluster.is_root:
        frame.to_parquet("runs/epidemic.parquet")
```

An error on one rank is raised on every rank, so a failed run stops instead of waiting forever.
With Dask and Ray the ghosts and migrants travel through the process that called `build`, a
round trip per exchange: fine for a few workers, slower than MPI for many. Install with
`pip install "modelly-abm[distributed]"` (mpi4py, which needs an MPI library: Open MPI or MPICH
on Linux and macOS, MS-MPI on Windows), `"modelly-abm[dask]"` or `"modelly-abm[ray]"`.

## Outputs and checkpoints

- `model.collect()` (or `cluster.collect()`): a pandas frame, one row per step and one for the
  build, with `time` and every reporter.
- `model.snapshot(("state", "days"))`: every agent by stream key with its location and the
  attributes named, equal to `modelly.distributed.snapshot(single_process_model, ...)`.
- `model.states()`: the full state of every agent, for exact comparisons.
- `model.checkpoint("runs/ckpt")` writes `part-00000.ckpt` ... one file per partition (a core
  checkpoint of its model, plus its layout) and `index.json` (the model class, the partitions,
  the time, the reporter rows so far and each file's SHA-256). `cluster.restore("runs/ckpt")`
  continues the run draw for draw, on any backend with the same number of workers; a file that
  no longer matches its digest is refused. Like every checkpoint, the files are pickles: only
  restore checkpoints you made or trust.

## Scaling, measured

`benchmarks/distributed/weak_scaling.py` measures weak scaling on the grid epidemic: every
worker owns a block of the same size with the same number of people, so perfect scaling keeps
the time per step constant, and the efficiency is `T(1) / T(K)`.

Next to each split run of K workers the script times K independent copies of one block's
model running at the same time with no communication at all, and keeps the slowest. That
separates what the machine gives (`T_copies(1) / T_copies(K)`) from what the split run keeps of
it (`T_copies(K) / T(K)`, the protocol's efficiency).

Measured on one laptop (Intel Core Ultra 7 356H, 16 cores of three kinds, Linux, Python
3.15, Open MPI 5.0, mpi4py 4.1) shared with other jobs: the load average before each run is in
the table. Wall-clock seconds per step after a warm-up step, the build excluded; the raw
numbers, with every copy's time, are in `benchmarks/distributed/results/`.

MPI, 10,000 people per worker (20 steps):

| workers | people | s/step split | s/step K copies | efficiency T(1)/T(K) | machine | protocol | load |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10,000 | 0.0151 | 0.0138 | 100% | 100% | 91% | 8.4 |
| 2 | 20,000 | 0.0244 | 0.0163 | 62% | 85% | 67% | 8.5 |
| 4 | 40,000 | 0.0421 | 0.0227 | 36% | 61% | 54% | 8.1 |
| 8 | 80,000 | 0.0745 | 0.0482 | 20% | 29% | 65% | 7.6 |
| 12 | 120,000 | 0.1113 | 0.0587 | 14% | 23% | 53% | 7.7 |
| 16 | 160,000 | 0.1723 | 0.0582 | 9% | 24% | 34% | 21.7 |

MPI, 40,000 people per worker (10 steps):

| workers | people | s/step split | s/step K copies | efficiency T(1)/T(K) | machine | protocol | load |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 40,000 | 0.0993 | 0.1006 | 100% | 100% | 101% | 4.7 |
| 2 | 80,000 | 0.1492 | 0.1623 | 67% | 62% | 109% | 4.4 |
| 4 | 160,000 | 0.2218 | 0.1759 | 45% | 57% | 79% | 4.4 |
| 8 | 320,000 | 0.3603 | 0.3139 | 28% | 32% | 87% | 4.6 |

Dask, 10,000 people per worker (20 steps), on a busier machine:

| workers | people | s/step split | s/step K copies | efficiency T(1)/T(K) | machine | protocol | load |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10,000 | 0.0572 | 0.0422 | 100% | 100% | 74% | 14.1 |
| 2 | 20,000 | 0.1875 | 0.0591 | 31% | 71% | 32% | 14.8 |
| 4 | 40,000 | 0.2161 | 0.0381 | 26% | 111% | 18% | 17.4 |
| 8 | 80,000 | 0.1374 | 0.0455 | 42% | 93% | 33% | 17.1 |

What this shows, and what it does not:

- **This laptop is not a cluster.** K copies of the same model with no communication already
  slow down to 24-32% of one copy at 8 to 16 processes (cores of different speeds, a shared
  memory bus, a lower all-core clock, other jobs). No split run can do better than that here.
- **The protocol keeps 53-91% of the machine with 10,000 people per worker** (34% at 16
  workers, when the load from other jobs tripled during the run) **and 79-109% with 40,000**:
  the exchange grows with a block's border, the work with its area, so larger blocks scale
  better. A step of this model costs about 1.5 microseconds per person, so the border
  traffic weighs heavily at small blocks; a model with more work per agent hides it better.
- **Dask pays a round trip through the coordinator** for every exchange (eight per step here):
  it is the backend that runs everywhere without MPI, not the fast one.
- **The 1.4 target, at least 70% weak scaling efficiency from 1 to 64 workers, is not measured.**
  It needs 64 cores of a cluster with a fast interconnect; one 16-core laptop cannot show it.
  Measured here, the split run's own efficiency against the machine's (the protocol column) is
  the part the code controls.

## Limits in 1.4

- Agents with `Column` state, models with events of their own and moves into cells with a
  capacity are refused.
- Each worker holds the whole space, and by default the whole initial population at build time
  (see `owns` above).
- Partitions are fixed at build: there is no load balancing while the run goes on.
- One worker runs one partition, and a restore needs the same number of partitions.
