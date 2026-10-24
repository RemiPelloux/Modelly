# Parallel runs

Run independent model runs over processes with the results in a deterministic order:
`run_batch` for any list of tasks, `run_grid` for a factorial design with one seed per run.
The output is the same as the sequential loop's, whatever the number of workers.

```{eval-rst}
.. automodule:: modelly.batch.runs
   :members: run_batch, run_grid, grid_tasks, default_workers
```
