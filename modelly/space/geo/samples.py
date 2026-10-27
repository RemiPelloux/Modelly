"""Small real geospatial samples, bundled so that models and tests run offline.

Three extracts of Burlington, Vermont, in ``modelly/space/geo/data``: the drivable streets
of downtown from OpenStreetMap (ODbL 1.0, © OpenStreetMap contributors), a 120 x 120 pixel
window of ESA WorldCover 10 m 2021 land cover (CC BY 4.0, © ESA WorldCover project 2021),
and the 41 census tracts of Chittenden County (U.S. Census Bureau, public domain). Their
sources, retrieval dates, changes and checksums are in ``data/NOTICE.md``;
``scripts/geo_data.py`` downloads the full sources, verifies their SHA-256 and cuts the
extracts again. None of them holds personal data.
"""

from __future__ import annotations

from pathlib import Path
from random import Random
from typing import TYPE_CHECKING, Any

from modelly.space.geo.raster import RasterLayer
from modelly.space.geo.roads import RoadNetwork

if TYPE_CHECKING:
    import geopandas as gpd

DATA = Path(__file__).resolve().parent / "data"
ROADS = DATA / "burlington_roads.graphml"
LANDCOVER = DATA / "burlington_landcover.tif"
TRACTS = DATA / "burlington_tracts.geojson"
NOTICE = DATA / "NOTICE.md"
TRACT_ID = "GEOID"

# ESA WorldCover 2021 classes, by pixel value.
WORLDCOVER_CLASSES = {
    10: "tree cover",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built-up",
    60: "bare or sparse vegetation",
    70: "snow and ice",
    80: "permanent water",
    90: "herbaceous wetland",
    95: "mangroves",
    100: "moss and lichen",
}


def sample_roads(crs: Any = None, random: Random | None = None) -> RoadNetwork:
    """The drivable streets of downtown Burlington as a ``RoadNetwork``.

    A strongly connected directed graph (one-way streets kept one-way) of 255 junctions,
    with edge ``length`` in metres and the OpenStreetMap ``highway`` class. Data
    © OpenStreetMap contributors, under the ODbL 1.0.

    Args:
        crs: the CRS to route in; by default the UTM zone of the streets (EPSG:32618).
        random: a seeded ``random.Random`` for the network's ``Network`` space.
    """
    import networkx as nx  # noqa: PLC0415 - optional dependency

    graph = nx.read_graphml(ROADS)
    return RoadNetwork(graph, crs=crs, random=random)


def sample_landcover() -> RasterLayer:
    """A 120 x 120 pixel window of ESA WorldCover 2021 (10 m) over Burlington's Intervale.

    Pixel values are WorldCover classes (``WORLDCOVER_CLASSES``); 0 is nodata. Data
    © ESA WorldCover project 2021, under CC BY 4.0.
    """
    return RasterLayer.from_file(LANDCOVER)


def sample_neighbourhoods() -> gpd.GeoDataFrame:
    """The 41 census tracts of Chittenden County, Vermont, indexed by their ``GEOID``.

    Columns ``NAME`` and ``ALAND`` (land area in square metres), in WGS 84. U.S. Census
    Bureau 2023 cartographic boundaries, public domain.
    """
    import geopandas as gpd  # noqa: PLC0415 - optional dependency

    return gpd.read_file(TRACTS).set_index(TRACT_ID)
