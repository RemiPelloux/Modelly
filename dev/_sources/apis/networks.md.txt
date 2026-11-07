# Networks

`modelly.space.networks` holds the temporal and multilayer networks, contact matrices, network
statistics and importers. It needs only numpy and scipy; NetworkX and igraph are used only to
convert from their graphs. The guide is [Networks](../networks.md). The static network cell
space, `Network`, is on the [Space](space.md#network) page.

| Module | Contents |
|---|---|
| `modelly.space.networks.temporal` | `TemporalNetwork`, `TemporalEdge` |
| `modelly.space.networks.multilayer` | `MultilayerNetwork` |
| `modelly.space.networks.contacts` | `contact_matrix`, `age_groups` |
| `modelly.space.networks.collectors` | degree distribution, clustering, components, `network_reporter` |
| `modelly.space.networks.io` | NetworkX, igraph and edge-list CSV import and export |
| `modelly.space.networks.base` | node rows shared by both network types |

## Temporal networks

```{eval-rst}
.. automodule:: modelly.space.networks.temporal
   :members:
```

## Multilayer networks

```{eval-rst}
.. automodule:: modelly.space.networks.multilayer
   :members:
```

## Contact matrices

```{eval-rst}
.. automodule:: modelly.space.networks.contacts
   :members:
```

## Network statistics

```{eval-rst}
.. automodule:: modelly.space.networks.collectors
   :members:
```

## Import and export

```{eval-rst}
.. automodule:: modelly.space.networks.io
   :members:
```

```{eval-rst}
.. automodule:: modelly.space.networks.base
   :members:
```
