# Distributed

One model split across processes or machines (provisional, new in 1.4), with the same results as one process for the same seed. The guide is [From laptop to cluster](https://remipelloux.github.io/Modelly/dev/distributed.html); the per-agent random streams it relies on are in [Determinism](https://remipelloux.github.io/Modelly/dev/determinism.html).

Module

Contents

modelly.distributed.cluster

Cluster (backends local, mpi, dask, ray), DistributedModel

modelly.distributed.contract

Partitionable, Phase, PartitionError, plan_of, run_phase

modelly.distributed.reduce

Sum, Min, Max, Reducer, snapshot

modelly.distributed.building

owns: build only a partition’s agents

modelly.distributed.verify

check_independence, single_process

modelly.distributed.partition

grid_blocks, GridBlocks, BlockLayout, Block, and graph, kd

modelly.distributed.graphs

graph, GraphPartition, GraphLayout

modelly.distributed.kdtree

kd, KDPartition, KDLayout, Box

modelly.distributed.checkpoints

the partition files and index.json of a split-run checkpoint

modelly.distributed.groups, modelly.distributed.remote

the backends: LocalGroup, MPIGroup, DaskGroup, RayGroup

modelly.distributed.worker

PartitionWorker, BuildRequest: one partition’s model and protocol

modelly.core.streams

the per-agent streams behind Model.agent_streams

`Cluster`: build a partitionable model split across workers, and run it.

```default
from modelly.distributed import Cluster, partition

with Cluster(backend="dask", workers=4) as cluster:
    model = cluster.build(Epidemic, scenario, partition=partition.grid_blocks(2, 2))
    model.run_for(365)
    cluster.collect().to_parquet("runs/epidemic.parquet")
```

Backends: `"local"` (every partition in this process, in turn), `"mpi"` (one partition per rank: run the script with `mpirun -n <partitions>`), `"dask"` and `"ray"` (one actor per partition). Under MPI every rank runs the same script and gets the same results; write files from `cluster.is_root` only.

#### `open_group(backend: str, requests: list[BuildRequest], options: dict) → Any`

The group of workers for `backend`.

#### `class DistributedModel(group: Any, model_class: type, rows: list | None = None)`

A model split across the workers of a group, stepped in lock step.

Run the model of `group`; `rows` continue a restored run.

#### `property time: float`

The model time of the last step.

#### `property partitions: int`

The number of partitions.

#### `step() → None`

One step: every phase, with its halo exchange and migration.

#### `run_for(steps: int) → None`

Run `steps` steps.

#### `collect() → DataFrame`

One row per step (the build included): the time and every reporter.

#### `info() → list[tuple[int, int, int, bool]]`

Per partition: agents built and kept, id counter, own stream keys.

#### `population() → list[int]`

The number of agents in each partition.

#### `snapshot(attributes: tuple[str, ...] = ()) → DataFrame`

Every agent by stream key, with its location and `attributes`.

#### `states() → list[tuple]`

The full state of every agent, in stream-key order (`reduce.states`).

#### `checkpoint(directory: str | Path) → Path`

Write one file per partition and `index.json` into `directory`.

#### `class Cluster(backend: str = 'local', workers: int | None = None, **options)`

Workers for split runs, on one backend (see the module docstring).

**Parameters:**

- **backend** – `"local"`, `"mpi"`, `"dask"` or `"ray"`.
- **workers** – the number of workers; `None` takes the partition count.
- ****options** – backend options: `comm` (MPI), `address` or `client` (Dask), `ray.init` arguments (Ray).

Keep the settings; workers start in `build` or `restore`.

#### `property is_root: bool`

Whether this process writes shared files (always, except MPI ranks > 0).

#### `build(model_class: type, scenario: Any, partition: Any) → DistributedModel`

Build `model_class(scenario=scenario)` split by `partition`.

**Raises:**

[**PartitionError**](https://remipelloux.github.io/Modelly/dev/apis/distributed.html#modelly.distributed.contract.PartitionError) – when the model is not partitionable, with the reason.

#### `restore(directory: str | Path) → DistributedModel`

Continue a run from `DistributedModel.checkpoint(directory)`.

#### `collect() → DataFrame`

The reporter rows of the last model built or restored.

#### `close() → None`

Stop the workers.

What a model declares so that it can be split across processes.

A partitionable model sets `agent_streams = True` and a class attribute `partitionable = Partitionable(space=..., phases=..., reporters=...)`, and its `step` runs the declared phases (`self.partitionable.step(self)`). Each phase is one method that every agent (of the phase’s types) runs, and the contract is what makes a split run draw and compute what one process does:

- a phase reads other agents only within its `radius` (cells, network hops or distance in a continuous space) and writes only the agent running it;
- the outcome of a phase does not depend on the order agents run in, nor on the order neighbours are listed (sort them by `stream_key()` if it must);
- every draw in a phase comes from the agent’s own streams (`self.random`, `self.rng`), never from the model’s generators;
- agents move only in phases declared with `moves=True`, and they migrate to the partition that owns their new location after the phase;
- agent attributes hold plain data, not references to agents, cells or the model.

`plan_of` and the checks of the distributed build refuse a model that breaks a part of the contract they can see; `check_independence` compares a split run with a single process for whatever they cannot.

#### `exception PartitionError`

A model cannot be split across processes, or a split run broke the contract.

#### `class Phase(method: str, radius: float = 0, moves: bool = False, types: tuple[type, ...] | None = None)`

One phase of a step: every agent (of `types`) calls `method`.

**Variables:**

- **method** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the agent method the phase calls.
- **radius** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – how far the method reads other agents (Chebyshev cells on a grid, hops on a network, distance in a continuous space); 0 reads only the agent itself and the agents in its own cell.
- **moves** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)) – whether the method may change the agent’s location.
- **types** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*type*](https://docs.python.org/3/builtins/functions.html#type)*, **...**] **| **None*) – the agent classes that run the phase (exact classes); all agents when `None`.

#### `run_phase(model: Model, phase: Phase) → None`

Call `phase.method` on the model’s agents (of `phase.types`).

#### `class Partitionable(space: str, phases: tuple[Phase, ...], reporters: Mapping[str, Reducer] = <factory>)`

The declaration that lets a model be split across processes.

**Variables:**

- **space** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the name of the model attribute holding the space to split (a grid, a `Network` or a `ContinuousSpace`).
- **phases** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)*[*[*Phase*](https://remipelloux.github.io/Modelly/dev/apis/distributed.html#modelly.distributed.contract.Phase)*, **...**]*) – the phases of one step, in order.
- **reporters** (*Mapping**[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*Reducer*](https://remipelloux.github.io/Modelly/dev/apis/distributed.html#modelly.distributed.reduce.Reducer)*]*) – name to reducer (`Sum`, `Min`, `Max`); each reducer’s function computes a partition’s part of the value from its model.

#### `step(model: Model) → None`

Run every phase once, in order: the model’s `step` on one process.

#### `report(model: Model) → dict[str, Any]`

The reporters’ values for one whole model (a single-process run).

#### `plan_of(model_class: type) → Partitionable`

The `Partitionable` of `model_class`, after the checks of its class.

**Raises:**

[**PartitionError**](https://remipelloux.github.io/Modelly/dev/apis/distributed.html#modelly.distributed.contract.PartitionError) – when the class declares none, or does not use agent streams.

Reporters that reduce across partitions, and agent snapshots in key order.

A reducer wraps a function of a (partition’s) model: `Sum(count_infected)` calls `count_infected` on every partition and adds the parts, `Min` and `Max` keep the smallest and largest. Integer sums, minima and maxima equal the single-process value exactly; a float sum is added with `math.fsum`, so it does not depend on the order of the parts, but each part is rounded before the parts are added: use integer reporters when byte identity matters.

`snapshot` lists agents by stream key with their location and attributes; the same call on a single-process model and on a split run gives equal frames.

#### `plain(value: Any) → Any`

`value` as a Python scalar when it is a numpy one (for JSON and equality).

#### `class Reducer(function: Callable[[Model], Any])`

A reporter: `function(model)` gives a partition’s part of the value.

#### `combine(parts: Sequence[Any]) → Any`

The whole value from the parts of every partition.

#### `class Sum(function: Callable[[Model], Any])`

The sum of the parts (`math.fsum` when any part is a float).

#### `combine(parts: Sequence[Any]) → Any`

Add the parts: exactly for integers, with `math.fsum` for floats.

#### `class Min(function: Callable[[Model], Any])`

The smallest part.

#### `combine(parts: Sequence[Any]) → Any`

The smallest part.

#### `class Max(function: Callable[[Model], Any])`

The largest part.

#### `combine(parts: Sequence[Any]) → Any`

The largest part.

#### `location_of(agent: Agent) → Any`

The agent’s place: its cell coordinate, or its position as a tuple of floats.

#### `records(agents: Iterable[Agent], attributes: Sequence[str]) → list[tuple]`

`(stream key, location, *attributes)` of each agent.

#### `states(agents: Iterable[Agent]) → list[tuple]`

`(stream key, location, pickled attributes and streams)` of each agent.

Two runs agree on an agent when these tuples are equal: every attribute and the state of its random streams, byte for byte.

#### `frame_of(rows: Iterable[tuple], attributes: Sequence[str]) → DataFrame`

The records as a frame indexed by stream key, in key order.

#### `snapshot(model: Model, attributes: Sequence[str] = ()) → pd.DataFrame`

The agents of a single-process model by stream key, with location and attributes.

Example

```default
>>> snapshot(model, ["state"])
```

Build only a partition’s agents: `owns(model, location)` in a model’s `__init__`.

By default every worker builds the whole initial population and then keeps its part, which costs the memory of the whole model in every worker while it builds. A model can build only what its partition owns instead:

```default
for key, cell in enumerate(cells):
    if owns(self, cell.coordinate):
        Person(self, cell, key=key)  # stream_key() returns key
```

`owns` is always `True` in a single process, so the model builds the same agents there. Agents built this way must override `stream_key()` with a key that does not depend on how many agents the process built (here the index in the single-process creation order); the build refuses a split model whose workers built different populations with the default keys. Grid blocks and graph parts can be asked during the build, as they depend on the space only; k-d boxes are computed from the built positions, so a `kd` split needs the whole population built.

#### `class Build(spec: Any, index: int, layout: Any = None)`

The partition a worker is building, and its layout once asked for.

#### `building(spec: Any, index: int) → Iterator[Build]`

Make `owns` answer for partition `index` of `spec` inside the block.

#### `owns(model: Any, location: Hashable) → bool`

Whether this process builds the agent at `location` (always, on one process).

**Raises:**

[**PartitionError**](https://remipelloux.github.io/Modelly/dev/apis/distributed.html#modelly.distributed.contract.PartitionError) – for a `kd` split, whose boxes need the built positions.

Check that a split run gives what one process gives, byte for byte.

`single_process` runs the model as anyone would, `model.step()` after `model.step()` in one process, and records its reporters and the full state of every agent. `check_independence` runs the same scenario split by each partition given, on the `local` backend, and raises at the first reporter value or agent state that differs, naming it. The partition-independence test suite is this check on reference models; run it on your own model before a long split run, since it catches what the build checks cannot see (a phase that reads past its radius, depends on the order of neighbours, or writes to another agent).

#### `class Run(rows: DataFrame, states: list[tuple])`

The outputs of a run: reporter rows and the state of every agent.

#### `single_process(model_class: type, scenario: Any, steps: int) → Run`

Run `model_class` in one process for `steps` steps from a copy of `scenario`.

#### `split_run(model_class: type, scenario: Any, partition: Any, steps: int) → Run`

Run `model_class` split by `partition` on the local backend.

#### `first_difference(reference: Run, other: Run) → str | None`

A description of the first output that differs, or `None`.

#### `check_independence(model_class: type, scenario: Any, partitions: Sequence[Any], steps: int) → Run`

Run one process and every split in `partitions`; raise if any output differs.

**Returns:**

The single-process run.

**Raises:**

[**PartitionError**](https://remipelloux.github.io/Modelly/dev/apis/distributed.html#modelly.distributed.contract.PartitionError) – naming the partition and the first differing output.

Split a space into partitions, one per worker, with their halos.

`grid_blocks` cuts a grid into rectangles (below), `graph` a network into parts with few edges between them (`modelly.distributed.graphs`) and `kd` a continuous space into boxes (`modelly.distributed.kdtree`). Each gives a layout that names the owner of a location and the halo of a partition.

Grid blocks, one per worker, with their halos.

`grid_blocks(rows, cols)` describes the split; `.layout(grid)` applies it to a grid’s dimensions and torus setting. A layout says which block owns a cell (`owner`, `owners`, `owner_map`) and which cells of other blocks lie within a radius of a block (`halo`): the ghost cells a worker must receive from its neighbours before a step that looks that far.

Each axis is cut into nearly equal runs, the larger runs first, so the same grid and split always give the same blocks, whichever process asks.

#### `class Block(index: int, lower: tuple[int, int], upper: tuple[int, int])`

One block: cells with `lower <= coordinate < upper` on every axis.

#### `property shape: tuple[int, int]`

Cells along each axis.

#### `cells() → Iterator[tuple[int, int]]`

The block’s coordinates, row by row.

#### `class GridBlocks(rows: int, cols: int)`

A split of a 2-D grid into `rows` by `cols` blocks.

#### `property partitions: int`

Number of blocks.

#### `layout(grid: Any = None, *, dimensions=None, torus=None) → BlockLayout`

The blocks of `grid` (or of explicit `dimensions` and `torus`).

#### `grid_blocks(rows: int, cols: int) → GridBlocks`

Split a 2-D grid into `rows` by `cols` rectangular blocks.

#### `class BlockLayout(dimensions, torus: bool, x_cuts, y_cuts)`

The blocks of one grid: who owns each cell, and each block’s halo.

Blocks bounded by `x_cuts` and `y_cuts`, numbered row-major.

#### `owners(coordinates: Iterable) → ndarray`

The index of the block owning each coordinate (an (n, 2) array or pairs).

#### `owner(coordinate: tuple[int, int]) → int`

The index of the block owning `coordinate`.

#### `property owner_map: ndarray`

Block index of every cell, shaped like the grid (read-only).

#### `halo(index: int, radius: int = 1) → frozenset[tuple[int, int]]`

Cells of other blocks within `radius` steps (Chebyshev) of block `index`.

#### `neighbours(index: int, radius: int = 1) → frozenset[int]`

Blocks owning a cell of block `index`’s halo.

Split a network into balanced parts with few edges between them.

`graph(parts)` describes the split; `.layout(network)` applies it to a `Network` (or a networkx graph). The method is deterministic: nodes are ordered by breadth-first search from a pseudo-peripheral node of each component (the banding order of Cuthill and McKee), the order is cut into `parts` runs of nearly equal size, the larger first, and a few passes of greedy boundary refinement (the k-way form of Fiduccia and Mattheyses) move a border node to the neighbouring part it has most edges to, while every part stays within `imbalance` of its target size. The same graph and node order give the same parts in every process.

A `GraphLayout` answers the questions of a `BlockLayout`: who owns a node (`owner`, `owners`) and which nodes of other parts lie within `radius` hops of a part (`halo`).

#### `neighbours_of(indptr: ndarray, indices: ndarray, nodes: ndarray)`

The neighbours of every node in `nodes`, concatenated (with repeats).

#### `banded_order(indptr: ndarray, indices: ndarray) → list[int]`

All nodes, component by component, each in BFS order from a far node.

#### `class GraphPartition(parts: int, imbalance: float = 0.03, passes: int = 4)`

A split of a network into `parts` parts (see the module docstring).

#### `property partitions: int`

Number of parts.

#### `layout(network: Any) → GraphLayout`

The parts of `network` (a `Network` or a networkx graph).

#### `graph(parts: int, imbalance: float = 0.03) → GraphPartition`

Split a network into `parts` balanced parts with few edges between them.

#### `class GraphLayout(nodes: list, assignment: ndarray, indptr, indices)`

The parts of one network: who owns each node, and each part’s halo.

Parts given by `assignment[i]` for `nodes[i]`, over CSR adjacency.

#### `owners(nodes: Iterable[Hashable]) → ndarray`

The part owning each node.

#### `owner(node: Hashable) → int`

The part owning `node`.

#### `sizes() → ndarray`

Nodes in each part.

#### `cut() → int`

Edges whose ends lie in different parts.

#### `halo(index: int, radius: int = 1) → frozenset`

Nodes of other parts within `radius` hops of part `index`.

#### `neighbours(index: int, radius: int = 1) → frozenset[int]`

Parts owning a node of part `index`’s halo.

Split a continuous space into boxes holding nearly equal numbers of agents.

`kd(parts)` describes the split; `.layout(space)` applies it to a `ContinuousSpace` from the positions of its agents. The domain is cut in two along its longest side (the lowest axis on ties) at the position that leaves `ceil(parts / 2) / parts` of the points on the low side, halfway between the two points either side of the cut; each side is cut again until there are `parts` boxes (recursive coordinate bisection, a k-d tree). The boxes cover the whole domain, so a point that moves anywhere has an owner.

A `KDLayout` says which box owns a point (`owner`, `owners`) and which points lie within a distance of a box (`near`, wrapping on a torus): the ghosts a worker sends before a phase that looks that far.

#### `class Box(index: int, lower: tuple[float, ...], upper: tuple[float, ...])`

One box: points with `lower <= x < upper` on every axis.

#### `class KDPartition(parts: int)`

A split of a continuous space into `parts` boxes (see the module docstring).

#### `property partitions: int`

Number of boxes.

#### `layout(space: Any = None, *, points=None, bounds=None) → KDLayout`

The boxes of `space` (or of explicit `points` and `bounds`).

#### `kd(parts: int) → KDPartition`

Split a continuous space into `parts` boxes of nearly equal population.

#### `class KDLayout(boxes: list[Box], torus: bool = False)`

The boxes of one continuous space: who owns a point, and who is near a box.

Boxes covering the domain, numbered in bisection order.

#### `owners(points: Any) → ndarray`

The box owning each point (an (n, d) array); the domain’s top edge included.

#### `owner(point: Any) → int`

The box owning `point`.

#### `distances(index: int, points: Any) → ndarray`

Euclidean distance from each point to box `index` (wrapping on a torus).

#### `reaches(index: int, lower: Any, upper: Any, radius: float) → bool`

Whether some point of the box `lower`..``upper`` may lie within `radius`.

False only when none can: rounding is monotone, so no point of the box is nearer box `index` than `distances` finds for the box itself (NaN bounds: True).

#### `near(index: int, points: Any, radius: float) → ndarray`

Whether each point lies within `radius` of box `index`.

Checkpoints of a split run: one file per partition plus an index.

`part-00003.ckpt` holds partition 3: a short header line and a pickle of its index, its layout and its model as a core checkpoint (`checkpoint_bytes`, so the Modelly and Python versions are checked the same way). `index.json` names the model class, the number of partitions, the time, the reporter rows so far and each file with its SHA-256; a restore checks every file against it.

Security: the files are pickles; only restore checkpoints you wrote or trust.

#### `digest(path: Path) → str`

The SHA-256 of a file, in hex.

#### `write_part(directory: Path, index: int, model: Any, layout: Any) → dict`

Write partition `index`; its entry for the index.

#### `read_part(path: Path, expected: str | None) → tuple[int, Any, Any]`

`(index, layout, model)` of a partition file, checked against its digest.

**Raises:**

[**CheckpointError**](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.CheckpointError) – when the file is not a partition checkpoint or has changed.

#### `class_path(model_class: type) → str`

`module:QualName` of a class.

#### `load_class(path: str) → type`

The class named by `class_path`.

#### `write_index(directory: Path, model_class: type, rows: list, files: list) → Path`

Write `index.json` for the partition files `files`.

#### `read_index(directory: str | Path) → dict`

The index of a split-run checkpoint.

**Raises:**

[**CheckpointError**](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.exceptions.CheckpointError) – when there is no index, or one of another format.

The workers of a split run and the way bytes travel between them.

A group calls the same worker method on every partition (`invoke` with the same arguments, `deliver` with one payload each), routes the outboxes the workers return to the inboxes of their receivers (`exchange`), and gives every process all the workers’ values in partition order (`gather`).

`LocalGroup` keeps every partition in this process and runs them one after the other: no parallelism, the reference for the other backends and the easiest to debug. `MPIGroup` is one partition per MPI rank (run the script under `mpirun -n <partitions>`); routing is one `alltoall` and an error on any rank is raised on every rank instead of leaving the others waiting.

#### `transpose(outboxes: dict[int, dict[int, bytes]]) → dict[int, dict[int, bytes]]`

Turn `{sender: {receiver: data}}` into `{receiver: {sender: data}}`.

#### `class LocalGroup(requests: Sequence[BuildRequest])`

Every partition in this process, run in turn.

Build one worker per request.

#### `invoke(method: str, *args: Any) → dict[int, Any]`

Call `method(*args)` on every worker.

#### `deliver(method: str, payloads: dict[int, Any]) → dict[int, Any]`

Call `method(payloads[i])` on worker `i`.

#### `static exchange(outboxes: dict[int, dict[int, bytes]]) → dict[int, dict[int, bytes]]`

Route every outbox to its receivers.

#### `gather(values: dict[int, Any]) → list[Any]`

The values in partition order.

#### `invoke_exchange(method: str, *args: Any) → dict[int, dict[int, bytes]]`

`exchange(invoke(method, *args))`: call, then route the outboxes.

#### `invoke_gather(method: str, *args: Any) → list[Any]`

`gather(invoke(method, *args))`: call, then the values in partition order.

#### `close() → None`

Drop the workers.

#### `class MPIGroup(requests: Sequence[BuildRequest], comm: Any = None)`

One partition per MPI rank of `comm` (`COMM_WORLD` by default).

Build this rank’s worker; the number of ranks must equal the partitions.

#### `invoke(method: str, *args: Any) → dict[int, Any]`

Call `method(*args)` on this rank’s worker.

#### `deliver(method: str, payloads: dict[int, Any]) → dict[int, Any]`

Call `method` on this rank’s worker with its payload.

#### `exchange(outboxes: dict[int, dict[int, bytes]]) → dict[int, dict[int, bytes]]`

Send each rank its part of this rank’s outbox; receive everyone’s.

#### `gather(values: dict[int, Any]) → list[Any]`

Every rank’s value, in rank order, on every rank.

#### `invoke_exchange(method: str, *args: Any) → dict[int, dict[int, bytes]]`

Call `method` and route its outbox in one `alltoall`, the status inside.

Each part carries the sender’s failure, if any, so every rank still learns of a failure on any rank and raises it, without a collective of its own.

#### `invoke_gather(method: str, *args: Any) → list[Any]`

Call `method` and gather every rank’s value in one `allgather`, as above.

#### `close() → None`

Drop this rank’s worker (MPI itself stays initialised for the script).

Split runs on Dask or Ray: each partition is an actor on a worker process.

The process that builds the model is the coordinator: it calls every actor in parallel and passes the ghosts and migrants between them, so the bytes of an exchange travel through it. That keeps the protocol identical to the MPI one, at the price of a round trip per exchange; for many partitions on a cluster prefer MPI, where neighbours talk directly.

`DaskGroup` starts a local cluster of one-thread worker processes (bound to 127.0.0.1, no dashboard) unless given an `address` or a `client`, and places one actor on each worker. `RayGroup` calls `ray.init` when Ray is not running yet and shuts it down afterwards. Both import their library only when used: `pip install "modelly-abm[dask]"` or `"modelly-abm[ray]"`.

#### `class DaskGroup(requests: Sequence[BuildRequest], **options: Any)`

One Dask actor per partition, each on a worker process of its own.

Connect (or start a local cluster) and start one actor per request.

#### `close() → None`

Drop the actors and close the client and cluster this group started.

#### `class RayGroup(requests: Sequence[BuildRequest], **options: Any)`

One Ray actor per partition.

Start Ray if needed, then one actor per request.

#### `close() → None`

Drop the actors, and shut Ray down when this group started it.

One partition of a split run: a model holding the agents of its part of space.

Every worker builds the model from the same scenario, so agents get the `unique_id` (and so the default stream key) of the single-process build, then keeps the agents its partition owns; a model that asks `owns()` builds only those in the first place. A step is the declared phases; around a phase that looks `radius` away, the worker sends copies of its border agents (ghosts) to its neighbours and receives theirs, and after a phase that moves agents it sends away those now standing on another partition’s ground (migrants, with their streams). Ghosts exist only during their phase.

The backends call these methods in the same order on every worker, and pass the bytes between them (`modelly.distributed.groups`).

#### `class BuildRequest(model_class: type | None, scenario: bytes | None, partition: Any, index: int, checkpoint: str | None = None, digest: str | None = None)`

What a worker needs to start: a model to build, or a checkpoint to load.

**Variables:**

- **model_class** ([*type*](https://docs.python.org/3/builtins/functions.html#type)* | **None*) – the partitionable model class.
- **scenario** ([*bytes*](https://docs.python.org/3/builtins/stdtypes.html#bytes)* | **None*) – the scenario, pickled (every worker starts from the same bytes).
- **partition** (*Any*) – the partition spec (`grid_blocks`, `graph`, `kd`).
- **index** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the partition this worker runs.
- **checkpoint** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – a partition file to restore instead of building.
- **digest** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)* | **None*) – the SHA-256 the checkpoint file must have.

#### `class PartitionWorker(request: BuildRequest)`

The model of one partition and the steps of the exchange protocol.

Build (or restore) the model, check it, and keep this partition’s agents.

#### `info() → tuple[int, int, int, bool]`

Agents built, agents kept, id counter after the build, own stream keys.

#### `begin_step() → None`

Advance the model’s time by one step, as its default schedule does.

#### `ghosts_for(phase: int) → dict[int, bytes]`

The ghosts each neighbour needs before `phase`.

#### `accept_ghosts(inbox: dict[int, bytes]) → None`

Place the neighbours’ ghosts, by sender then in the sender’s order.

#### `act(phase: int) → dict[int, bytes]`

Run `phase` on the local agents; the migrants, for a moving phase.

#### `accept_migrants(inbox: dict[int, bytes]) → None`

Register the arriving agents, by sender then in the sender’s order.

#### `report() → tuple[float, dict[str, Any]]`

The model’s time and this partition’s part of every reporter.

#### `snapshot(attributes: tuple[str, ...]) → list[tuple]`

`(stream key, location, *attributes)` of the local agents.

#### `states() → list[tuple]`

The full state of every local agent (see `reduce.states`).

#### `save(directory: str) → dict`

Write this partition’s checkpoint file; its entry for the index.

Per-agent random streams: each agent draws from generators of its own.

A model opts in with `agent_streams = True` on its class. `agent.random` and `agent.rng` then come from a seed derived from the model’s seed and the agent’s stream key (its `unique_id` unless `stream_key` is overridden), so an agent’s draws do not depend on how many draws other agents made or on the order in which agents step. This is what lets a population split across processes give the same results as one process: an agent takes its stream with it. Without the flag, every agent shares `model.random` and `model.rng` as before.

The seed of key `k` is `SeedSequence(entropy, spawn_key=(*root, DOMAIN, k))` where `entropy` and `root` are the scenario’s seed sequence: replicates of a scenario get different streams, and no stream equals one that `SeedSequence.spawn` hands out, since spawned keys never reach `DOMAIN`. The generators are created on an agent’s first draw and travel with it in checkpoints and pickles.

#### `stream_seed(agent: Agent) → np.random.SeedSequence`

The seed sequence of `agent`’s own streams.

#### `own_random(agent: Agent) → Random`

`agent`’s stdlib-compatible generator, created on first use.

#### `own_rng(agent: Agent) → np.random.Generator`

`agent`’s numpy generator, of the scenario’s bit generator, created on first use.
