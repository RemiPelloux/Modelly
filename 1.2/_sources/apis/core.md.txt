# Core

`modelly.core` holds the model, agents, agent sets, columns, the random source and the
exceptions. `modelly.Model`, `modelly.Agent`, `modelly.Column` and `modelly.FastRandom` are the
same objects as `modelly.core.Model`, `modelly.core.Agent` and so on.

| Module | Contents |
|---|---|
| `modelly.core.model` | `Model` |
| `modelly.core.registry` | the agent registries the model inherits (`agents`, `agents_by_type`, `agent_types`) |
| `modelly.core.agent` | `Agent` |
| `modelly.core.agentset` | `AgentSet`, `AbstractAgentSet`, `GroupBy` |
| `modelly.core.columns`, `modelly.core.column_access` | `Column` and the column tables |
| `modelly.core.rng` | `FastRandom`, `PyFastRandom` |
| `modelly.core.checkpoint` | the checkpoint file format behind `Model.save` and `Model.load` |
| `modelly.core.exceptions` | the exceptions raised by Modelly |

## Model

`Model` takes its agent registries from `modelly.core.registry`, its scheduling methods from
`modelly.time.schedule` and its signals from `modelly.time.signals`; all of them are listed
below.

```{eval-rst}
.. automodule:: modelly.core.model
   :members:
   :inherited-members:
```

## Agent

```{eval-rst}
.. automodule:: modelly.core.agent
   :members:
```

## Agent sets

`AgentSet` takes its selection methods (`select`, `select_random`) from
`modelly.core.agentset.selection` and its attribute methods (`get`, `set`, `agg`) from
`modelly.core.agentset.attributes`; they are listed under `AgentSet`.

```{eval-rst}
.. automodule:: modelly.core.agentset.weak
   :members:
   :inherited-members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.core.agentset.abstract
   :members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.core.agentset.groupby
   :members:
```

## Columns

Columnar agent state: declare a `Column` on an `Agent` subclass and that attribute lives in a
model-owned numpy array, readable per agent and as a whole.

```{eval-rst}
.. automodule:: modelly.core.columns
   :members:
```

Per-agent access: on the class, each column is a property that reads the agent's row through a
`memoryview` (see `Agent.column_specs()` for the declarations).

```{eval-rst}
.. automodule:: modelly.core.column_access
   :members:
```

## Random numbers

`model.random` is a `FastRandom`: a `random.Random` that gives exactly the standard library's
numbers for a seed, faster. When the compiled core is built for the interpreter (platform
wheels for Linux and macOS, or `bash scripts/build-native.sh` in a checkout), `randint`,
`choice`, `shuffle`, `sample` and `_randbelow` run in C on CPython's own Mersenne Twister state;
otherwise `FastRandom` is `PyFastRandom`, the pure-Python version. `modelly.core.rng.NATIVE` says
which one is in use, and `MODELLY_PURE_PYTHON=1` forces the Python one.

```{eval-rst}
.. automodule:: modelly.core.rng
   :members: FastRandom, PyFastRandom, NATIVE
```

## Checkpoints

`Model.save`, `Model.load` and `Model.checkpoint_every` (listed under `Model`) write and read
this format; see [Checkpoints](../checkpoints.md).

```{eval-rst}
.. automodule:: modelly.core.checkpoint
   :members: save_model, load_model, CheckpointWriter
```

## Exceptions

```{eval-rst}
.. automodule:: modelly.core.exceptions
   :members:
   :show-inheritance:
```
