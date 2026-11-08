# Batch

`modelly.batch` runs many independent model runs and holds counted populations.

| Module | Contents |
|---|---|
| `modelly.batch.runs` | `run_batch`, `run_grid` |
| `modelly.batch.cohorts` | `CohortTable` |

## Parallel runs

Run independent model runs over processes with the results in a deterministic order:
`run_batch` for any list of tasks, `run_grid` for a factorial design with one seed per run.
The output is the same as the sequential loop's, whatever the number of workers.

```{eval-rst}
.. automodule:: modelly.batch.runs
   :members: run_batch, run_grid, grid_tasks, default_workers
```

## Cohorts

A counted population: one row per state (stage, age, sex...) with a `count`, and every
per-individual draw replaced by one binomial draw per row with exactly the same law. See
[Vectorised step phases](../vectorised_phases.md) for the argument.

```{eval-rst}
.. automodule:: modelly.batch.cohorts
   :members:
```
