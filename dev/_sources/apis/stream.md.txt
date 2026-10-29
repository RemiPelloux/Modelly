# Stream

Live observations for running models (provisional, new in 1.4): sources that hand out
observations as they arrive, observation operators that read the same quantities from a
model, ensembles of replicates advanced in lock step, and the filters that keep an ensemble
close to the observations. The [data assimilation tutorial](../assimilation.md) walks through
all of them on a synthetic truth.

| Module | Contents |
|---|---|
| `modelly.stream.sources` | `Observation`, `ReplaySource`, `CSVSource`, `HTTPSource`, `due` |
| `modelly.stream.connectors` | `MQTTSource` (extra `mqtt`), `KafkaSource` (extra `kafka`) |
| `modelly.stream.operators` | `ObservationOperator` |
| `modelly.stream.ensemble` | `Ensemble`, `derived_seed`, `replicate_scenarios` |
| `modelly.stream.particle` | `ParticleFilter`, `FilterStep`, `systematic_resample`, `effective_sample_size` |
| `modelly.stream.kalman` | `EnsembleKalmanFilter`, `enkf_update` |
| `modelly.stream.bands` | `forecast_band`, `weighted_quantiles`, `quantile_column` |

Methods: the bootstrap particle filter of Gordon, Salmond & Smith (1993) with systematic
resampling (Douc & Cappé 2005); the stochastic ensemble Kalman filter of Evensen (1994, 2003)
with perturbed observations (Burgers, van Leeuwen & Evensen 1998). Full references are in the
tutorial.

Bands (`Ensemble.band`, `Ensemble.forecast`, `ParticleFilter.band`, `ParticleFilter.forecast`)
are long-format DataFrames with the columns `time`, `quantity`, `mean` and one `q<level>` per
quantile (`q0.05`, `q0.5`, `q0.95` by default): plain data for plots and live views.

```{eval-rst}
.. automodule:: modelly.stream.sources
   :members:
```

```{eval-rst}
.. automodule:: modelly.stream.connectors
   :members:
```

```{eval-rst}
.. automodule:: modelly.stream.operators
   :members:
```

```{eval-rst}
.. automodule:: modelly.stream.ensemble
   :members:
```

```{eval-rst}
.. automodule:: modelly.stream.particle
   :members:
```

```{eval-rst}
.. automodule:: modelly.stream.kalman
   :members:
```

```{eval-rst}
.. automodule:: modelly.stream.bands
   :members:
```
