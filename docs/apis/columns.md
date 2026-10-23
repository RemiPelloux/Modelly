# Columns

Columnar agent state: declare a `Column` on an `Agent` subclass and that attribute lives in a
model-owned numpy array, readable per agent and as a whole.

```{eval-rst}
.. automodule:: modelly.columns
   :members:
```

Per-agent access: on the class, each column is a property that reads the agent's row through a
`memoryview` (see `Agent.column_specs()` for the declarations).

```{eval-rst}
.. automodule:: modelly.column_access
   :members:
```
