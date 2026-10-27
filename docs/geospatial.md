# Geospatial models

`modelly.space.geo` starts a model from real maps: census zones as polygons, land cover as a
raster, streets as a routable network, and a synthetic population drawn from census tables.

```bash
pip install "modelly-abm[geo]"         # GeoPandas, Shapely, pyproj, rasterio
pip install "modelly-abm[geo,osm]"     # and OSMnx, to download OpenStreetMap streets
```

GeoPandas, Shapely, pyproj and rasterio ship wheels for Windows, macOS and Linux that bundle
GDAL and PROJ, so nothing has to be installed on the system. Importing `modelly.space.geo`
without them raises an `ImportError` that names the extra. Writing GeoParquet also needs
`pyarrow`.

## One coordinate reference system, set at the space

A `GeoSpace` works in one projected CRS, so that distances are in metres (or feet), not
degrees. The CRS is chosen once, when the space is created:

- `GeoSpace(regions, crs="EPSG:2154")` uses the CRS you name and reprojects `regions`;
- `GeoSpace(regions)` uses the CRS of `regions`, or, when that is geographic (latitude and
  longitude, such as EPSG:4326), the UTM zone that covers them.

Everything that comes in later can carry its own CRS and is reprojected: `GeoAgent(space,
model, point, crs="EPSG:4326")`, `space.move_to(agent, point, crs=...)`,
`space.project(geometry, crs=...)` and `space.project_points(xy, crs=...)`.

```python
import geopandas as gpd

from modelly import Model
from modelly.space.geo import GeoAgent, GeoSpace

zones = gpd.read_file("zones.gpkg").set_index("zone_id")  # any CRS


class Resident(GeoAgent):
    pass


model = Model(rng=42)
space = GeoSpace(zones, random=model.random)
home = space.random_points("Z042", 1, model.rng)[0]
resident = Resident(space, model, home)
resident.region  # "Z042"
resident.move_to((2.35, 48.85), crs="EPSG:4326")  # a longitude and latitude
```

## Agents as points, polygons as regions

`GeoSpace` is a `ContinuousSpace`: every agent's position is a row of one numpy array
(`space.agent_positions`), and the continuous space's KD-tree queries work in metres:
`get_agents_in_radius`, `neighbors_within(radius)` (every agent's neighbours in one call) and
`get_k_nearest_agents`. The regions are the rows of `space.regions`, a GeoDataFrame indexed
by region label, with one STRtree over their polygons.

| Question | Call |
|---|---|
| Which region is this point in? | `space.region_of(point)`; `space.regions_of(xy)` for many |
| Which agents are in region `r`? | `space.agents_in_region(r)`; `space.region_counts()` for all |
| Which agents are inside this polygon, or within 500 m of this line? | `space.agents_within(geometry)`, `space.agents_within(geometry, distance=500)` |
| Which regions border `r`? | `space.region_neighbors(r)` (queen), `kind="rook"` for a shared edge |
| Which regions are within 2 km of `r`? | `space.region_neighbors(r, distance=2000)` |
| Region adjacency as a matrix | `space.contiguity("queen")`, a scipy CSR matrix |

Region membership of the agents is computed for the whole population at once and cached until
an agent moves.

## Export

`space.to_geodataframe()` gives one point per agent with its `unique_id`, its `region` and any
attributes you name; `space.to_geodataframe("regions")` gives the regions with an `n_agents`
column. `space.to_file(path)` writes either one, chosen by suffix: `.parquet` for GeoParquet,
`.geojson` for GeoJSON (in WGS 84, as the format requires). Both open in QGIS and in GeoPandas.

```python
space.to_file("residents.parquet", attributes=("age", "income"))
space.to_file("zones.geojson", what="regions")
```

## Rasters as property layers

A `RasterLayer` holds one band with its affine transform, CRS and nodata value. Its `values`
are shaped like an orthogonal grid, `(width, height)`, with `y` increasing northward, so the
band can be a grid's property layer: the grid and the raster then share one array.

```python
from modelly.space.geo import RasterLayer

land = RasterLayer.from_file("landcover.tif")
grid = land.to_grid("cover", random=model.random)  # an OrthogonalMooreGrid
grid[(10, 4)].cover  # the pixel under cell (10, 4)
land.sample_agents(space)  # the value under every GeoAgent, nan outside or on nodata
land.to_file("landcover-after.tif")  # writes the band back as a GeoTIFF
```

`land.sample(xy, crs=...)` samples at any points, reprojecting them if needed;
`land.reproject("EPSG:3035")` warps the band into another CRS.

## Road networks and routing

A `RoadNetwork` wraps any NetworkX graph whose nodes have `x` and `y` coordinates, the OSMnx
convention, and gives every node a cell of a `Network` space (`roads.space`), so agents can
also stand on intersections as `CellAgent`s. Edges without a `length` get the straight-line
length.

```python
from modelly.space.geo import RoadNetwork, download_osm

roads = RoadNetwork(graph, random=model.random)  # graph.graph["crs"] is honoured
roads.add_travel_times(speed=13.9)  # length / speed, unless an edge has its own speed
path = roads.shortest_path(home, work, weight="travel_time")  # nodes or points
minutes = roads.travel_time(home, work) / 60
# scipy, many sources at once
matrix = roads.distance_matrix(origins, weight="travel_time")
near = roads.agents_within(space, origin, 1000)  # agents within 1 km along the streets

# needs the osm extra and a connection
lyon = download_osm("Lyon, France", random=model.random)
```

`download_osm` downloads; cache the graph (`osmnx.save_graphml`) instead of calling it on
every run. After changing edge attributes yourself, call `roads.invalidate()` so the next
`distance_matrix` is rebuilt.

## Synthetic populations

Census tables give, per region, the number of people in each level of each attribute, not
the joint table. `ipf(seed, marginals)` fits a joint table to the marginals by iterative
proportional fitting, keeping the seed's zeros; `synthesize_population` does it per region
and returns one row per person:

```python
from modelly.space.geo import synthesize_population

people = synthesize_population(
    {"age": ["0-17", "18-64", "65+"], "car": [True, False]},
    {"Z042": {"age": [210, 600, 190], "car": [700, 300]}, ...},
    model.rng,
)
for zone, group in people.groupby("region"):
    for point, age in zip(space.random_points(zone, len(group), model.rng), group.age):
        Resident(space, model, point).age = age
```

Each region gets exactly its total and its first attribute's counts; the other marginals are
met to within the rounding (the fitted table is rounded to whole people at random, from
`model.rng`, so a seed gives the same people). The full toolkit, with households, homes,
schools, workplaces and contact networks, is `modelly.population`: see
[Synthetic populations](population.md). The two functions above are the same in both places.

## Real-data samples

`modelly.space.geo.samples` bundles three small extracts of Burlington, Vermont, so that models
and tests on real data run offline. None holds personal data.

| Call | Returns | Source and licence |
|---|---|---|
| `sample_roads()` | a `RoadNetwork` of the drivable streets of downtown: 255 junctions, one-way streets kept | OpenStreetMap, ODbL 1.0, © OpenStreetMap contributors |
| `sample_landcover()` | a `RasterLayer` of 120 x 120 ESA WorldCover 2021 pixels (10 m) over the Intervale | ESA WorldCover, CC BY 4.0, © ESA WorldCover project 2021 |
| `sample_neighbourhoods()` | the 41 census tracts of Chittenden County as a GeoDataFrame | U.S. Census Bureau, public domain |

The files are in `modelly/space/geo/data`, with their sources, retrieval dates, changes and
checksums in `NOTICE.md` there. The OpenStreetMap extract is a derived database under the
ODbL: a database you make from it must be offered under the ODbL as well. To fetch the full
sources, check their SHA-256 and cut the extracts again (the same commands in bash and
PowerShell):

```text
python scripts/geo_data.py download data/raw    fetch and verify the full sources
python scripts/geo_data.py verify data/raw      verify sources already downloaded
python scripts/geo_data.py build data/raw       rebuild the bundled extracts (geo extra)
```

The full sources are the Census Bureau's 2023 tract boundaries of Vermont (112 KB), the
WorldCover tile N42W075 (65 MB) and an Overpass query of the streets pinned to
2026-10-01. The query's checksum is over its elements, sorted, so the server's own timestamp in
the reply does not change it.

## Zoo models on real data

Three zoo models run on the samples by default and take your own data through their scenario:

- [Traffic assignment](zoo/road_traffic.md) (`road_traffic`): random trips routed by shortest
  path over the OpenStreetMap streets; flows match the exact edge betweenness.
  `RoadTrafficScenario(roads=RoadNetwork(graph))` runs it on another street graph.
- [Habitat selection](zoo/habitat_selection.md) (`habitat_selection`): animals disperse over
  the WorldCover raster and settle in proportion to habitat preference.
  `HabitatScenario(cover=RasterLayer.from_file(path).values)` runs it on another raster.
- [Schelling on real neighbourhoods](zoo/schelling_regions.md) (`schelling_regions`): two
  groups move between census tracts, neighbours by contiguity.
  `SchellingRegionsScenario(adjacency=GeoSpace(regions).contiguity())` runs it on other
  regions.

## Checkpoints

`GeoSpace`, `RasterLayer` and `RoadNetwork` are saved by `model.save` and restored by
`Model.load` like any other part of the model (see [Checkpoints](checkpoints.md)). The STRtree,
the contiguity matrices, the cached region membership and the routing matrices are not saved
but rebuilt on first use. A raster attached to a grid stays shared with it after a load.

## Example

[Commuting City](https://github.com/RemiPelloux/Modelly/tree/main/modelly/examples/spatial/commuting_city)
puts it together on generated data: zones of a synthetic city, residents from a synthetic
population, workplaces by a gravity rule over travel times, and congested routing on a street
lattice. The [API reference](apis/geo.md) lists every class and function.
