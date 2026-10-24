# Scenarios

`modelly.scenarios` describes the parameters of a run as a typed `Scenario` (with its seed),
runs many scenarios and keeps their results in a `Store`.

| Module | Contents |
|---|---|
| `modelly.scenarios.scenario` | `Scenario` |
| `modelly.scenarios.runner` | `run_scenarios`, `RunConfiguration` |
| `modelly.scenarios.sampling` | `rescale_samples` |
| `modelly.scenarios.store` | `Store`, `RunId`, `RunRecord` and the in-memory store |
| `modelly.scenarios.exceptions` | the exceptions raised while running scenarios |

## Scenario

```{eval-rst}
.. automodule:: modelly.scenarios.scenario
   :members:
```

## Running scenarios

```{eval-rst}
.. automodule:: modelly.scenarios.runner
   :members:
```

```{eval-rst}
.. automodule:: modelly.scenarios.sampling
   :members:
```

## Storing results

```{eval-rst}
.. automodule:: modelly.scenarios.store
   :members:
```

## Exceptions

```{eval-rst}
.. automodule:: modelly.scenarios.exceptions
   :members:
   :show-inheritance:
```
