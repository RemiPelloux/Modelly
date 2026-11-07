# Experiments

`modelly.experiments` runs parameter studies: a space, a design, replicates and outputs, on any
executor, into a resumable Parquet store. How to use it is in
[Experiments and sweeps](../experiments.md).

| Module | Contents |
|---|---|
| `modelly.experiments.experiment` | `Experiment`, `RunReport`, `ExperimentError` |
| `modelly.experiments.space` | `ScenarioSpace`, `Range`, `Choice`, `Fixed` |
| `modelly.experiments.designs` | full factorial, Latin hypercube, Sobol, Halton, custom |
| `modelly.experiments.store` | `ResultsStore`, `Results` |
| `modelly.experiments.tasks` | `RunTask`, `RunOutcome`, `run_task` |
| `modelly.experiments.executors` | the registry and the executors |
| `modelly.experiments.spec` | TOML experiment files |
| `modelly.experiments.worker` | the job-array entry point |

## Experiment

```{eval-rst}
.. automodule:: modelly.experiments.experiment
   :members:
```

## Parameter space

```{eval-rst}
.. automodule:: modelly.experiments.space
   :members:
```

## Designs

```{eval-rst}
.. automodule:: modelly.experiments.designs
   :members:
```

## Results store

```{eval-rst}
.. automodule:: modelly.experiments.store
   :members:
```

## Runs

```{eval-rst}
.. automodule:: modelly.experiments.tasks
   :members:
```

## Executors

```{eval-rst}
.. automodule:: modelly.experiments.executors
   :members:
```

```{eval-rst}
.. automodule:: modelly.experiments.executors.local
   :members:
```

```{eval-rst}
.. automodule:: modelly.experiments.executors.dask_executor
   :members:
```

```{eval-rst}
.. automodule:: modelly.experiments.executors.ray_executor
   :members:
```

```{eval-rst}
.. automodule:: modelly.experiments.executors.cluster
   :members:
```

## Experiment files and the worker

```{eval-rst}
.. automodule:: modelly.experiments.spec
   :members:
```

```{eval-rst}
.. automodule:: modelly.experiments.worker
   :members:
```
