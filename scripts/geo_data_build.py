"""Cut the bundled Burlington samples from the verified full sources (see geo_data.py).

Needs the ``geo`` extra (GeoPandas, rasterio, pyproj) and NetworkX. Called by
``python scripts/geo_data.py build DIR``; not meant to be run on its own.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pyproj
import rasterio
import shapely
from rasterio.windows import Window

STATE_TRACTS = "cb_2023_50_tract_500k.zip"
COUNTY = "007"  # Chittenden County, Vermont
TRACT_COLUMNS = ["GEOID", "NAME", "ALAND", "geometry"]
WGS84 = "EPSG:4326"
DECIMALS = 6  # about 0.1 m: shared borders stay shared, the file stays small

WORLDCOVER = "ESA_WorldCover_10m_2021_v200_N42W075_Map.tif"
LANDCOVER_ORIGIN = (-73.215, 44.505)  # longitude, latitude of the north-west corner
LANDCOVER_PIXELS = 120  # 120 x 120 pixels of 1/12000 degree, about 1.2 km a side

OSM = "burlington_osm.json"
ONE_WAY = ("yes", "true", "1")
REVERSED = "-1"
LENGTH_DECIMALS = 2

TRACTS_OUT = "burlington_tracts.geojson"
LANDCOVER_OUT = "burlington_landcover.tif"
ROADS_OUT = "burlington_roads.graphml"


def build_all(sources: Path, target: Path) -> None:
    """Write the three samples into ``target`` from the sources in ``sources``."""
    build_tracts(sources / STATE_TRACTS, target / TRACTS_OUT)
    build_landcover(sources / WORLDCOVER, target / LANDCOVER_OUT)
    build_roads(sources / OSM, target / ROADS_OUT)


def build_tracts(source: Path, target: Path) -> None:
    """The census tracts of Chittenden County in WGS 84, coordinates rounded."""
    tracts = gpd.read_file(f"zip://{source}")
    county = tracts[tracts.COUNTYFP == COUNTY][TRACT_COLUMNS].to_crs(WGS84)
    county = county.sort_values("GEOID").reset_index(drop=True)
    county["geometry"] = shapely.transform(
        county.geometry.values, lambda xy: np.round(xy, DECIMALS)
    )
    county.to_file(target, driver="GeoJSON")


def build_landcover(source: Path, target: Path) -> None:
    """A window of the WorldCover tile, unchanged pixels, as an uncompressed GeoTIFF.

    Uncompressed because Pyodide's GDAL reads no Deflate; at 120 x 120 bytes the file
    is small either way.
    """
    with rasterio.open(source) as tile:
        row, column = tile.index(*LANDCOVER_ORIGIN)
        window = Window(column, row, LANDCOVER_PIXELS, LANDCOVER_PIXELS)
        band = tile.read(1, window=window)
        profile = tile.profile | {
            "width": LANDCOVER_PIXELS,
            "height": LANDCOVER_PIXELS,
            "transform": tile.window_transform(window),
            "tiled": False,
        }
        for key in ("blockxsize", "blockysize", "compress", "predictor"):
            profile.pop(key, None)
    with rasterio.open(target, "w", **profile) as out:
        out.write(band, 1)


def build_roads(source: Path, target: Path) -> None:
    """The drivable streets as a strongly connected directed graph, lengths in metres."""
    elements = json.loads(source.read_text(encoding="utf-8"))["elements"]
    points = {e["id"]: (e["lon"], e["lat"]) for e in elements if e["type"] == "node"}
    ways = [e for e in elements if e["type"] == "way"]
    graph = nx.DiGraph(crs=WGS84)
    geod = pyproj.Geod(ellps="WGS84")
    junctions = _junctions(ways)
    for way in sorted(ways, key=lambda w: w["id"]):
        for piece in _pieces(way["nodes"], junctions):
            _add_piece(graph, piece, way["tags"], points, geod)
    largest = max(nx.strongly_connected_components(graph), key=len)
    graph = graph.subgraph(sorted(largest)).copy()
    nx.write_graphml(graph, target)


def _junctions(ways: list[dict]) -> set[int]:
    """Nodes where a way ends or that two ways share: the graph's nodes."""
    used = Counter(node for way in ways for node in set(way["nodes"]))
    ends = {way["nodes"][k] for way in ways for k in (0, -1)}
    return ends | {node for node, count in used.items() if count > 1}


def _pieces(nodes: list[int], junctions: set[int]) -> list[list[int]]:
    """A way split at its junctions, each piece from one junction to the next."""
    pieces, current = [], [nodes[0]]
    for node in nodes[1:]:
        current.append(node)
        if node in junctions:
            pieces.append(current)
            current = [node]
    return pieces


def _add_piece(graph: nx.DiGraph, piece, tags, points, geod) -> None:
    """Add one street piece, both ways unless it is one-way; keep the shorter duplicate."""
    start, end = piece[0], piece[-1]
    if start == end:
        return
    lons, lats = zip(*(points[n] for n in piece))
    length = round(geod.line_length(lons, lats), LENGTH_DECIMALS)
    oneway = tags.get("oneway", "no")
    pairs = [(start, end), (end, start)]
    if oneway in ONE_WAY or tags.get("junction") == "roundabout":
        pairs = pairs[:1]
    elif oneway == REVERSED:
        pairs = pairs[1:]
    for u, v in pairs:
        for node in (u, v):
            graph.add_node(str(node), x=points[node][0], y=points[node][1])
        old = graph.get_edge_data(str(u), str(v))
        if old is None or old["length"] > length:
            graph.add_edge(str(u), str(v), length=length, highway=tags["highway"])
