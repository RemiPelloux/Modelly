# Geospatial space

`modelly.space.geo` needs the optional `geo` extra (`pip install "modelly-abm[geo]"`);
`download_osm` also needs the `osm` extra. The guide is [Geospatial models](../geospatial.md).

| Module | Contents |
|---|---|
| `modelly.space.geo.space` | `GeoSpace`: agents as points, polygons as regions, one CRS |
| `modelly.space.geo.regions` | region neighbourhoods: contiguity and distance |
| `modelly.space.geo.agents` | `GeoAgent` |
| `modelly.space.geo.raster` | `RasterLayer`: a raster band as a grid property layer |
| `modelly.space.geo.roads` | `RoadNetwork`, `download_osm` |
| `modelly.space.geo.population` | `ipf`, `synthesize_population` |
| `modelly.space.geo.export` | GeoDataFrames of a space, GeoParquet and GeoJSON output |

## GeoSpace

`GeoSpace` is a `ContinuousSpace`: it also has `get_agents_in_radius`, `neighbors_within` and
`get_k_nearest_agents`, listed under [Continuous space](space.md#continuous-space).

```{eval-rst}
.. automodule:: modelly.space.geo.space
   :members:
   :show-inheritance:
```

```{eval-rst}
.. automodule:: modelly.space.geo.regions
   :members:
```

```{eval-rst}
.. automodule:: modelly.space.geo.agents
   :members:
   :show-inheritance:
```

## Rasters

```{eval-rst}
.. automodule:: modelly.space.geo.raster
   :members:
```

## Road networks

```{eval-rst}
.. automodule:: modelly.space.geo.roads
   :members:
```

## Synthetic populations

```{eval-rst}
.. automodule:: modelly.space.geo.population
   :members:
```

## Export

```{eval-rst}
.. automodule:: modelly.space.geo.export
   :members:
```
