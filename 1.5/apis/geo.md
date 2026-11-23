# Geospatial space

`modelly.space.geo` needs the optional `geo` extra (`pip install "modelly-abm[geo]"`); `download_osm` also needs the `osm` extra. The guide is [Geospatial models](https://remipelloux.github.io/Modelly/geospatial.html).

Module

Contents

modelly.space.geo.space

GeoSpace: agents as points, polygons as regions, one CRS

modelly.space.geo.regions

region neighbourhoods: contiguity and distance

modelly.space.geo.agents

GeoAgent

modelly.space.geo.raster

RasterLayer: a raster band as a grid property layer

modelly.space.geo.roads

RoadNetwork, download_osm

modelly.space.geo.population

ipf, synthesize_population: deprecated aliases of modelly.population

modelly.space.geo.samples

the bundled Burlington streets, land cover and census tracts

modelly.space.geo.export

GeoDataFrames of a space, GeoParquet and GeoJSON output

## GeoSpace

`GeoSpace` is a `ContinuousSpace`: it also has `get_agents_in_radius`, `neighbors_within` and `get_k_nearest_agents`, listed under [Continuous space](https://remipelloux.github.io/Modelly/apis/space.html#continuous-space).

A vector geospatial space: agents as points, polygons as regions, one CRS.

`GeoSpace` is a `ContinuousSpace` whose coordinates are those of a projected coordinate reference system (metres for UTM), so the continuous space’s KD-tree queries (`get_agents_in_radius`, `neighbors_within`, `get_k_nearest_agents`) measure real distances. Agent positions stay one numpy array; regions are the rows of a GeoDataFrame, indexed by an STRtree for point-in-polygon and distance lookups.

The CRS is set once, at the space. Inputs that carry another CRS (regions, points, geometries) are reprojected into it; a geographic CRS (latitude and longitude) is replaced by the UTM zone that covers the regions, since degrees are not distances.

#### `class GeoSpace(regions: GeoDataFrame | None = None, crs: Any = None, random: Random | None = None, *, bounds: Sequence[float] | None = None, n_agents: int = 100)`

Bases: [`RegionQueriesMixin`](https://remipelloux.github.io/Modelly/apis/geo.html#modelly.space.geo.regions.RegionQueriesMixin), [`ContinuousSpace`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.continuous.space.ContinuousSpace)

Agents as points and polygons as regions, in one projected CRS.

**Variables:**

- **crs** – the space’s `pyproj.CRS`, or `None` for plain planar coordinates.
- **regions** – a GeoDataFrame of the region polygons in `crs`; its index labels the regions.

Create a geospatial space.

**Parameters:**

- **regions** – polygons that make up the study area, in any CRS; reprojected to `crs`.
- **crs** – the space’s CRS (anything `pyproj.CRS` accepts). Defaults to the CRS of `regions`, or to its UTM zone when that CRS is geographic.
- **random** – a seeded `random.Random`, usually `model.random`.
- **bounds** – `(minx, miny, maxx, maxy)` in `crs`; defaults to the regions’ bounds.
- **n_agents** – the expected number of agents, to size the position array.

#### `project(geometry: Any, crs: Any = None) → Any`

Return `geometry` in the space’s CRS.

**Parameters:**

- **geometry** – a Shapely geometry, a GeoSeries or a GeoDataFrame.
- **crs** – the CRS `geometry` is in; GeoPandas objects default to their own CRS. `None` for a Shapely geometry means it is already in the space’s CRS.

#### `project_points(xy: ndarray, crs: Any = None) → ndarray`

Return an `(n, 2)` array of coordinates in `crs` reprojected to the space’s CRS.

#### `move_to(agent: Agent, point: Any, crs: Any = None) → None`

Move `agent` to `point` (a Shapely `Point` or `(x, y)`, in `crs`).

#### `region_of(point: Any, crs: Any = None) → Any`

Return the label of the region containing `point`, or `None` outside all regions.

#### `regions_of(xy: ndarray) → ndarray`

Region row (position in `regions`) of every point in `xy`; `-1` outside.

A point on a shared border belongs to the region listed first.

#### `agent_regions() → ndarray`

Region row of every agent, in `active_agents` order; cached until an agent moves.

#### `agents_in_region(label: Any) → list[Agent]`

The agents whose position lies in the region labelled `label`.

#### `region_counts() → Series`

Number of agents in every region, indexed by region label.

#### `agents_within(target: Any, distance: float | None = None, crs: Any = None) → list[Agent]`

The agents inside `target`, or within `distance` of it.

**Parameters:**

- **target** – a Shapely geometry or an `(x, y)` point.
- **distance** – in the space’s units; `None` means inside (or on) `target` itself.
- **crs** – the CRS of `target`, if not the space’s.

#### `random_points(label: Any, n: int, rng: Generator) → ndarray`

`n` points drawn uniformly inside region `label`, as an `(n, 2)` array.

**Parameters:**

- **label** – the region label.
- **n** – the number of points.
- **rng** – a numpy generator, usually `model.rng`.

#### `to_geodataframe(what: str = 'agents', attributes: Sequence[str] = ()) → GeoDataFrame`

The agents (as points, with `attributes`) or the regions (with agent counts).

#### `to_file(path: str | Path, what: str = 'agents', attributes: Sequence[str] = ()) → Path`

Write `to_geodataframe(what, attributes)` as GeoParquet or GeoJSON, by suffix.

`.parquet` and `.geoparquet` write GeoParquet (needs `pyarrow`); `.geojson` and `.json` write GeoJSON in WGS 84, as the GeoJSON standard asks.

Region neighbourhoods of a `GeoSpace`: contiguity (queen, rook) and distance.

#### `class RegionQueriesMixin`

Neighbourhoods between the polygons of `regions`, built on one STRtree.

Relies on the host providing `regions` (a GeoDataFrame), and the cache slots `_region_tree_cache` and `_contiguity_cache`.

#### `contiguity(kind: str = 'queen') → csr_matrix`

The region adjacency as a symmetric CSR matrix, rows in `regions` order.

**Parameters:**

**kind** – `"queen"`: regions sharing at least one point are neighbours; `"rook"`: they must share a border of positive length.

#### `region_neighbors(label: Any, kind: str = 'queen', distance: float | None = None) → list`

Labels of the regions next to region `label`.

**Parameters:**

- **label** – the region label.
- **kind** – `"queen"` or `"rook"` contiguity, used when `distance` is `None`.
- **distance** – if given, every other region within this distance of `label`.

#### `regions_within(geometry: Any, distance: float | None = None) → list`

Labels of the regions that intersect `geometry`, or lie within `distance` of it.

Agents located at a point of a `GeoSpace`.

#### `class GeoAgent(space: GeoSpace, model: Model, position: Any = None, crs: Any = None)`

Bases: [`ContinuousSpaceAgent`](https://remipelloux.github.io/Modelly/apis/space.html#modelly.space.continuous.agents.ContinuousSpaceAgent)

An agent at a point of a `GeoSpace`; its position is a row of the position array.

**Variables:**

- **space** ([*GeoSpace*](https://remipelloux.github.io/Modelly/apis/geo.html#modelly.space.geo.space.GeoSpace)) – the space the agent is in.
- **position** (*np.ndarray*) – `(x, y)` in the space’s CRS.

Place a new agent in `space`.

**Parameters:**

- **space** – the geospatial space.
- **model** – the model the agent belongs to.
- **position** – a Shapely `Point` or `(x, y)`; defaults to the centre of the space.
- **crs** – the CRS of `position`, if not the space’s.

#### `move_to(point: Any, crs: Any = None) → None`

Move to `point` (a Shapely `Point` or `(x, y)`, in `crs`).

#### `property region: Any`

The label of the region the agent is in, or `None`.

#### `property geometry: Point`

The agent’s position as a Shapely `Point`.

## Rasters

Rasters as property layers: a GeoTIFF band aligned to a grid space.

A `RasterLayer` keeps one band in `values`, shaped like an orthogonal grid (`(width, height)`, indexed `[x, y]` with `y = 0` the southern row), so it can be attached to a grid as a property layer: `cell.<name>` and the raster share one array, and a vectorised update of the layer is a raster update. The affine `transform` maps pixel `(column, row)` of the north-up band to map coordinates in `crs`, as in rasterio.

#### `class RasterLayer(data: ndarray, transform: Any, crs: Any = None, nodata: Any = None)`

One raster band with its transform, CRS and nodata value.

**Variables:**

- **values** – the band, shape `(width, height)`, indexed `[x, y]` with `y` northward.
- **transform** – the `affine.Affine` from pixel `(column, row)` to map coordinates.
- **crs** – the `pyproj.CRS` of the map coordinates, or `None`.
- **nodata** – the value marking missing cells, or `None`.

Wrap a north-up band (rows from north to south, as rasterio reads it).

**Parameters:**

- **data** – a 2-D array, shape `(rows, columns)`.
- **transform** – an `affine.Affine`, or its six coefficients `(a, b, c, d, e, f)`.
- **crs** – anything `pyproj.CRS` accepts.
- **nodata** – the value of missing cells.

#### `property shape: tuple[int, int]`

the dimensions of a grid aligned to the raster.

**Type:**

`(width, height)`

#### `property array: ndarray`

a view of `values`.

**Type:**

The band north-up, shape `(rows, columns)`

#### `classmethod from_file(path: str | Path, band: int = 1) → RasterLayer`

Read one band of a raster file (GeoTIFF or any format rasterio reads).

#### `to_file(path: str | Path) → Path`

Write the band, with its transform, CRS and nodata value, as a GeoTIFF.

#### `cells_of(xy: ndarray, crs: Any = None) → ndarray`

Grid coordinate `(x, y)` of the cell under every point, `-1` outside.

**Parameters:**

- **xy** – an `(n, 2)` array of map coordinates.
- **crs** – the CRS of `xy` when it differs from the raster’s.

#### `sample(xy: ndarray, crs: Any = None) → ndarray`

The raster value under every point, as floats; `nan` outside or on nodata.

#### `sample_agents(space: GeoSpace) → np.ndarray`

The raster value at every agent of `space`, in `active_agents` order.

#### `cell_centers() → ndarray`

Map coordinates of every cell centre, shape `(width, height, 2)`.

#### `attach(grid: HasPropertyLayers, name: str, read_only: bool = False) → None`

Attach `values` to `grid` as property layer `name` (shared, not copied).

#### `to_grid(name: str, random: Random | None = None, **kwargs) → OrthogonalMooreGrid`

A new `OrthogonalMooreGrid` of the raster’s shape with the band as layer `name`.

Extra keyword arguments (`torus`, `capacity`, …) go to the grid.

#### `reproject(crs: Any, resampling: str = 'nearest') → RasterLayer`

A new layer warped to `crs` with rasterio (`resampling` names the method).

## Road networks

Road networks: a NetworkX graph with node coordinates as a `Network` space, and routing.

Nodes carry their coordinates as `x` and `y` attributes (the OSMnx convention) and edges a `length`; edges without one get the straight-line length between their ends. The graph is reprojected once into the network’s CRS. Agents can stand on its nodes as `CellAgent``s of ``space`, and route with NetworkX (one pair) or scipy (many sources).

#### `class RoadNetwork(graph: Any, crs: Any = None, random: Random | None = None, weight: str = 'length')`

A road graph in one projected CRS, its `Network` space and shortest paths.

**Variables:**

- **graph** – the NetworkX graph (any of Graph, DiGraph, MultiGraph, MultiDiGraph).
- **crs** – the `pyproj.CRS` of the node coordinates, or `None`.
- **space** – a `Network` space with one cell per node, at the node’s coordinates.
- **weight** – the default edge attribute for routing.

Wrap `graph`; its own CRS is `graph.graph["crs"]`, as OSMnx sets it.

**Parameters:**

- **graph** – a NetworkX graph whose nodes have `x` and `y` attributes.
- **crs** – the CRS to route in; defaults to the graph’s, or its UTM zone if geographic.
- **random** – a seeded `random.Random` for the `Network` space.
- **weight** – the default edge attribute shortest paths minimise.

#### `node_of(point: Any) → Any`

`point` itself if it is a node, else the node nearest to it (`Point` or `(x, y)`).

#### `nearest_nodes(xy: ndarray) → ndarray`

Row (position in `nodes`) of the node nearest to every point of `xy`.

#### `shortest_path(origin: Any, destination: Any, weight: str | None = None) → list`

The nodes of a shortest path; `origin` and `destination` are nodes or points.

#### `path_length(origin: Any, destination: Any, weight: str | None = None) → float`

The total `weight` of a shortest path between two nodes or points.

#### `travel_time(origin: Any, destination: Any) → float`

The shortest travel time between two nodes or points (see `add_travel_times`).

#### `add_travel_times(speed: float) → None`

Set `travel_time = length / speed` on every edge.

**Parameters:**

**speed** – in CRS units per unit of model time, for edges without a `speed` attribute of their own.

#### `distances_from(origin: Any, cutoff: float | None = None, weight: str | None = None) → dict`

Shortest `weight` from `origin` to every node reachable within `cutoff`.

#### `distance_matrix(origins: Any, weight: str | None = None) → ndarray`

Shortest `weight` from every origin (nodes or points) to every node, with scipy.

**Returns:**

an array of shape `(len(origins), len(nodes))`; unreachable nodes are `inf`.

#### `routing_matrix(weight: str | None = None) → csr_matrix`

The graph as a CSR matrix of `weight`, rows in `nodes` order.

Parallel edges keep the smallest weight; an undirected edge counts both ways.

#### `invalidate(weight: str | None = None) → None`

Forget the routing matrix of `weight` (all when `None`) after edges changed.

#### `path_geometry(path: list) → LineString`

The polyline through the coordinates of the nodes of `path`.

#### `agents_within(space: GeoSpace, origin: Any, distance: float, weight: str | None = None) → list[Agent]`

The agents of `space` whose nearest node is within network `distance` of `origin`.

#### `download_osm(place: str, network_type: str = 'drive', crs: Any = None, random: Random | None = None) → RoadNetwork`

Download the road network of `place` from OpenStreetMap (needs the `osm` extra).

Edges get OSMnx’s `speed_kph` and `travel_time` (seconds) attributes. This makes a network request: cache the result (`osmnx.save_graphml`) rather than calling it per run.

## Synthetic populations

`modelly.space.geo.population` keeps `ipf` and `synthesize_population` importable from their 1.3 home, with a deprecation warning (removed in 2.0); they are documented, with the rest of the toolkit, under [Synthetic populations](https://remipelloux.github.io/Modelly/apis/population.html).

## Bundled samples

Small real geospatial samples, bundled so that models and tests run offline.

Three extracts of Burlington, Vermont, in `modelly/space/geo/data`: the drivable streets of downtown from OpenStreetMap (ODbL 1.0, © OpenStreetMap contributors), a 120 x 120 pixel window of ESA WorldCover 10 m 2021 land cover (CC BY 4.0, © ESA WorldCover project 2021), and the 41 census tracts of Chittenden County (U.S. Census Bureau, public domain). Their sources, retrieval dates, changes and checksums are in `data/NOTICE.md`; `scripts/geo_data.py` downloads the full sources, verifies their SHA-256 and cuts the extracts again. None of them holds personal data.

#### `sample_roads(crs: Any = None, random: Random | None = None) → RoadNetwork`

The drivable streets of downtown Burlington as a `RoadNetwork`.

A strongly connected directed graph (one-way streets kept one-way) of 255 junctions, with edge `length` in metres and the OpenStreetMap `highway` class. Data © OpenStreetMap contributors, under the ODbL 1.0.

**Parameters:**

- **crs** – the CRS to route in; by default the UTM zone of the streets (EPSG:32618).
- **random** – a seeded `random.Random` for the network’s `Network` space.

#### `sample_landcover() → RasterLayer`

A 120 x 120 pixel window of ESA WorldCover 2021 (10 m) over Burlington’s Intervale.

Pixel values are WorldCover classes (`WORLDCOVER_CLASSES`); 0 is nodata. Data © ESA WorldCover project 2021, under CC BY 4.0.

#### `sample_neighbourhoods() → gpd.GeoDataFrame`

The 41 census tracts of Chittenden County, Vermont, indexed by their `GEOID`.

Columns `NAME` and `ALAND` (land area in square metres), in WGS 84. U.S. Census Bureau 2023 cartographic boundaries, public domain.

## Export

GeoDataFrames of a `GeoSpace` and writing them as GeoParquet or GeoJSON.

#### `agents_frame(space: GeoSpace, attributes: Sequence[str] = ()) → gpd.GeoDataFrame`

One row per agent: `unique_id`, `region`, the named attributes and a point.

#### `regions_frame(space: GeoSpace) → gpd.GeoDataFrame`

The regions with an `n_agents` column counting the agents in each.

#### `write_frame(frame: GeoDataFrame, path: Path) → Path`

Write `frame` to `path`: GeoParquet or GeoJSON, chosen by the suffix.
