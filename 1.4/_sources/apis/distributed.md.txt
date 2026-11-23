# Distributed

One model split across processes or machines (provisional, new in 1.4), with the same results
as one process for the same seed. The guide is [From laptop to cluster](../distributed.md); the
per-agent random streams it relies on are in [Determinism](../determinism.md).

| Module | Contents |
|---|---|
| `modelly.distributed.cluster` | `Cluster` (backends `local`, `mpi`, `dask`, `ray`), `DistributedModel` |
| `modelly.distributed.contract` | `Partitionable`, `Phase`, `PartitionError`, `plan_of`, `run_phase` |
| `modelly.distributed.reduce` | `Sum`, `Min`, `Max`, `Reducer`, `snapshot` |
| `modelly.distributed.building` | `owns`: build only a partition's agents |
| `modelly.distributed.verify` | `check_independence`, `single_process` |
| `modelly.distributed.partition` | `grid_blocks`, `GridBlocks`, `BlockLayout`, `Block`, and `graph`, `kd` |
| `modelly.distributed.graphs` | `graph`, `GraphPartition`, `GraphLayout` |
| `modelly.distributed.kdtree` | `kd`, `KDPartition`, `KDLayout`, `Box` |
| `modelly.distributed.checkpoints` | the partition files and `index.json` of a split-run checkpoint |
| `modelly.distributed.groups`, `modelly.distributed.remote` | the backends: `LocalGroup`, `MPIGroup`, `DaskGroup`, `RayGroup` |
| `modelly.distributed.worker` | `PartitionWorker`, `BuildRequest`: one partition's model and protocol |
| `modelly.core.streams` | the per-agent streams behind `Model.agent_streams` |

```{eval-rst}
.. automodule:: modelly.distributed.cluster
   :members:
```

```{eval-rst}
.. automodule:: modelly.distributed.contract
   :members:
```

```{eval-rst}
.. automodule:: modelly.distributed.reduce
   :members:
```

```{eval-rst}
.. automodule:: modelly.distributed.building
   :members:
```

```{eval-rst}
.. automodule:: modelly.distributed.verify
   :members:
```

```{eval-rst}
.. automodule:: modelly.distributed.partition
   :members: grid_blocks, GridBlocks, BlockLayout, Block
```

```{eval-rst}
.. automodule:: modelly.distributed.graphs
   :members:
```

```{eval-rst}
.. automodule:: modelly.distributed.kdtree
   :members:
```

```{eval-rst}
.. automodule:: modelly.distributed.checkpoints
   :members:
```

```{eval-rst}
.. automodule:: modelly.distributed.groups
   :members:
```

```{eval-rst}
.. automodule:: modelly.distributed.remote
   :members:
```

```{eval-rst}
.. automodule:: modelly.distributed.worker
   :members:
```

```{eval-rst}
.. automodule:: modelly.core.streams
   :members:
```
