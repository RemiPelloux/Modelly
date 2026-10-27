"""Reference models for split runs (``modelly.distributed``).

One model per kind of space, each written to the contract of
``modelly.distributed.contract``: ``GridEpidemic`` (a torus grid, split with
``partition.grid_blocks``), ``NetworkSIR`` (a small-world network, split with
``partition.graph``) and ``ContinuousSIR`` (a continuous torus, split with
``partition.kd``). The partition-independence tests and the scaling benchmark
run them.
"""
