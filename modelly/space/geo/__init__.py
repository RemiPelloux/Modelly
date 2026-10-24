"""Geospatial space: real maps, rasters, road networks and census-style populations.

``modelly.space.geo`` needs the optional ``geo`` extra (GeoPandas, Shapely, pyproj and
rasterio, which ship wheels for Windows, macOS and Linux; no system GDAL is needed)::

    pip install "modelly-abm[geo]"

Road networks downloaded from OpenStreetMap need the ``osm`` extra (OSMnx) as well.

Key components:

- ``GeoSpace``: a vector space in one projected coordinate reference system, with
  agents as points (``GeoAgent``) and polygons as regions.
- ``RasterLayer``: a raster as a property layer of a grid, sampled at agent positions.
- ``RoadNetwork``: a road graph as a ``Network`` space, with shortest-path routing.
- ``synthesize_population``: a synthetic population per region from marginal tables.
"""

from modelly.space.geo._deps import require

require("geopandas", "geo")
require("shapely", "geo")
require("pyproj", "geo")

from modelly.space.geo.agents import GeoAgent  # noqa: E402
from modelly.space.geo.population import ipf, synthesize_population  # noqa: E402
from modelly.space.geo.raster import RasterLayer  # noqa: E402
from modelly.space.geo.roads import RoadNetwork, download_osm  # noqa: E402
from modelly.space.geo.space import GeoSpace  # noqa: E402

__all__ = [
    "GeoAgent",
    "GeoSpace",
    "RasterLayer",
    "RoadNetwork",
    "download_osm",
    "ipf",
    "synthesize_population",
]
