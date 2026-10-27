"""Distributed simulation: one model split across processes (provisional, 1.4).

A model that declares ``partitionable = Partitionable(space=..., phases=...)``
and uses per-agent streams (``agent_streams = True``) can be built split across
workers, with the same results as one process for the same seed::

    from modelly.distributed import Cluster, partition

    with Cluster(backend="dask", workers=4) as cluster:
        model = cluster.build(Epidemic, scenario, partition=partition.grid_blocks(2, 2))
        model.run_for(365)
        cluster.collect().to_parquet("runs/epidemic.parquet")

``partition`` cuts grids (``grid_blocks``), networks (``graph``) and continuous
spaces (``kd``); the workers exchange ghost agents at partition borders before
a phase that looks across them and migrate agents after a phase that moves
them. Backends: ``local``, ``mpi`` (mpi4py), ``dask`` and ``ray``. The
contract a model meets is in ``modelly.distributed.contract`` and in the guide
"From laptop to cluster"; ``check_independence`` compares a split run with one
process.
"""

from modelly.distributed import partition
from modelly.distributed.cluster import Cluster, DistributedModel
from modelly.distributed.contract import Partitionable, PartitionError, Phase
from modelly.distributed.graphs import GraphLayout, GraphPartition, graph
from modelly.distributed.kdtree import KDLayout, KDPartition, kd
from modelly.distributed.partition import Block, BlockLayout, GridBlocks, grid_blocks
from modelly.distributed.reduce import Max, Min, Reducer, Sum, snapshot
from modelly.distributed.verify import check_independence, single_process

__all__ = [
    "Block",
    "BlockLayout",
    "Cluster",
    "DistributedModel",
    "GraphLayout",
    "GraphPartition",
    "GridBlocks",
    "KDLayout",
    "KDPartition",
    "Max",
    "Min",
    "PartitionError",
    "Partitionable",
    "Phase",
    "Reducer",
    "Sum",
    "check_independence",
    "graph",
    "grid_blocks",
    "kd",
    "partition",
    "single_process",
    "snapshot",
]
