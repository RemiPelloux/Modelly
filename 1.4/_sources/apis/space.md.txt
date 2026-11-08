# Space

`modelly.space` holds the discrete cell spaces (grids, networks, Voronoi meshes), continuous
space, property layers and the integer cell index. The names most models need are exported by
the package itself: `from modelly.space import OrthogonalMooreGrid, CellAgent`.

| Module | Contents |
|---|---|
| `modelly.space.cells` | `Cell`, `CellCollection`, the cell agents, `CellIndex`, `Occupancy` |
| `modelly.space.base` | `DiscreteSpace`, the base of every discrete space |
| `modelly.space.grid` | `Grid`, `OrthogonalMooreGrid`, `OrthogonalVonNeumannGrid`, `HexGrid`, property layers |
| `modelly.space.network` | `Network` |
| `modelly.space.voronoi`, `modelly.space.delaunay` | `VoronoiGrid` and the triangulation behind it |
| `modelly.space.continuous` | `ContinuousSpace`, `ContinuousSpaceAgent`, vectorised helpers |

## Cells

`Cell` takes its neighbourhood methods (`neighborhood`, `get_neighborhood`) from
`modelly.space.cells.neighborhood`; they are listed under `Cell`.

```{eval-rst}
.. automodule:: modelly.space.cells.cell
   :members:
   :inherited-members:
```

```{eval-rst}
.. automodule:: modelly.space.cells.collection
   :members:
```

## Cell agents

```{eval-rst}
.. automodule:: modelly.space.cells.agents
   :members:
   :show-inheritance:
```

## Discrete spaces

```{eval-rst}
.. automodule:: modelly.space.base
   :members:
```

### Grids

```{eval-rst}
.. automodule:: modelly.space.grid.base
   :members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.space.grid.grids
   :members:
   :show-inheritance:
```

### Property layers

Grids take `create_property_layer`, `add_property_layer` and `remove_property_layer` from this
mixin.

```{eval-rst}
.. automodule:: modelly.space.grid.layers
   :members:
```

### Network

```{eval-rst}
.. automodule:: modelly.space.network
   :members:
   :show-inheritance:
```

### Voronoi

```{eval-rst}
.. automodule:: modelly.space.voronoi
   :members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.space.delaunay
   :members:
```

## Integer cells: index, occupancy and row-placed agents

```{eval-rst}
.. automodule:: modelly.space.cells.index
   :members:
```

```{eval-rst}
.. automodule:: modelly.space.cells.occupancy
   :members:
```

## Continuous space

`ContinuousSpace` takes its neighbour queries (`get_agents_in_radius`, `neighbors_within`,
`get_k_nearest_agents`) from `modelly.space.continuous.queries`; they are listed under
`ContinuousSpace`.

```{eval-rst}
.. automodule:: modelly.space.continuous.space
   :members:
   :inherited-members:
```

```{eval-rst}
.. automodule:: modelly.space.continuous.agents
   :members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.space.continuous.vectorised
   :members:
```
