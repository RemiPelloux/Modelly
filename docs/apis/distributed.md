# Distributed

Planning a split of one model across processes (provisional, new in 1.4). The workers, halo
exchange and migration are not written yet; what exists is the partition plan and the
per-agent random streams a split run needs (`Model.agent_streams`,
[Determinism](../determinism.md)).

| Module | Contents |
|---|---|
| `modelly.distributed.partition` | `grid_blocks`, `GridBlocks`, `BlockLayout`, `Block` |
| `modelly.core.streams` | the per-agent streams behind `Model.agent_streams` |

```{eval-rst}
.. automodule:: modelly.distributed.partition
   :members:
```

```{eval-rst}
.. automodule:: modelly.core.streams
   :members:
```
