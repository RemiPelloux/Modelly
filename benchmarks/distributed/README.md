# Weak scaling of split runs

`weak_scaling.py` times the grid epidemic of `modelly.examples.distributed` split into
grid blocks, with the same block size and the same number of people per worker at every
worker count. Perfect weak scaling keeps the time per step constant; the efficiency is
`T(1) / T(K)`.

```bash
python benchmarks/distributed/weak_scaling.py --backend mpi --workers 1 2 4 8 16 --people 10000
python benchmarks/distributed/weak_scaling.py --backend dask --workers 1 2 4 8 --people 10000
```

Each worker builds only its block's people (`owns`), but holds the whole grid, so memory per
worker grows with the worker count. The time is wall-clock seconds per step on rank 0 (or the
Dask coordinator), after one warm-up step, the build excluded. The JSON files in `results/`
hold every run with the machine's load average before it; the guide
[From laptop to cluster](../../docs/distributed.md) discusses them.
