# Data

`modelly.data` holds two ways to collect data from a run: the `DataCollector` (model, agent,
agent-type and table reporters, called once per step) and the dataset recorders of
`modelly.data.recorders` (named datasets recorded on a schedule into memory, JSON, Parquet or
SQL).

| Module | Contents |
|---|---|
| `modelly.data.collector` | `DataCollector` |
| `modelly.data.reporters` | reporter normalisation and the row-collection paths |
| `modelly.data.io` | Arrow and Parquet export, DuckDB queries |
| `modelly.data.recorders` | `DataRegistry`, the datasets and the recorders |

## DataCollector

`DataCollector` takes `add_table_row` from `modelly.data.tables` and the `get_*_dataframe`
methods from `modelly.data.frames`; they are listed under `DataCollector`.

```{eval-rst}
.. automodule:: modelly.data.collector
   :members:
   :inherited-members:
```

## Arrow, Parquet and DuckDB

`DataCollector.to_arrow` and `DataCollector.to_parquet` call these functions; `query` runs SQL
over Arrow tables, DataFrames and Parquet files. They need `pip install "modelly-abm[experiments]"`.

```{eval-rst}
.. automodule:: modelly.data.io
   :members: to_arrow, to_parquet, write_parquet_atomic, query, tables_of
```

## Reporters

The functions behind the collector: reporter normalisation and the fast row-collection paths.

```{eval-rst}
.. automodule:: modelly.data.reporters
   :members:
```

## Datasets

```{eval-rst}
.. automodule:: modelly.data.recorders.registry
   :members:
```

```{eval-rst}
.. automodule:: modelly.data.recorders.protocol
   :members:
```

```{eval-rst}
.. automodule:: modelly.data.recorders.object_datasets
   :members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.data.recorders.numpy_dataset
   :members:
```

## Recorders

```{eval-rst}
.. automodule:: modelly.data.recorders.config
   :members:
```

```{eval-rst}
.. automodule:: modelly.data.recorders.base
   :members:
```

```{eval-rst}
.. automodule:: modelly.data.recorders.memory
   :members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.data.recorders.json_recorder
   :members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.data.recorders.parquet
   :members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.data.recorders.sql
   :members:
   :show-inheritance:
```
