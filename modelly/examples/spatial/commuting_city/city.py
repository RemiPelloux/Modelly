"""A synthetic city: square zones, a lattice of streets with two fast avenues.

Everything is generated, so the example runs offline. To use a real city, replace
``city_zones`` with census zones read by ``geopandas.read_file`` and ``street_graph``
with ``modelly.space.geo.download_osm("Lyon, France")``.
"""

import geopandas as gpd
import networkx as nx
import shapely

CRS = "EPSG:32631"  # UTM zone 31N, metres
ORIGIN = (640_000.0, 5_070_000.0)  # south-west corner of the city in that CRS
STREET_SPEED = 8.0  # metres per second
AVENUE_SPEED = 16.0


def city_zones(blocks: int, block_size: float) -> gpd.GeoDataFrame:
    """``blocks x blocks`` square zones labelled ``z<i>_<j>``; the central ones are the centre."""
    x0, y0 = ORIGIN
    rows = []
    middle = (blocks - 1) / 2
    for i in range(blocks):
        for j in range(blocks):
            box = shapely.box(
                x0 + i * block_size,
                y0 + j * block_size,
                x0 + (i + 1) * block_size,
                y0 + (j + 1) * block_size,
            )
            central = abs(i - middle) < 1 and abs(j - middle) < 1
            rows.append({"zone": f"z{i}_{j}", "centre": central, "geometry": box})
    return gpd.GeoDataFrame(rows, crs=CRS).set_index("zone")


def street_graph(blocks: int, block_size: float) -> nx.Graph:
    """Streets along the zone edges; the middle row and column are fast avenues."""
    x0, y0 = ORIGIN
    graph = nx.grid_2d_graph(blocks + 1, blocks + 1)
    for (i, j), data in graph.nodes(data=True):
        data["x"] = x0 + i * block_size
        data["y"] = y0 + j * block_size
    avenue = blocks // 2
    for u, v, data in graph.edges(data=True):
        on_avenue = (u[0] == v[0] == avenue) or (u[1] == v[1] == avenue)
        data["speed"] = AVENUE_SPEED if on_avenue else STREET_SPEED
    graph.graph["crs"] = CRS
    return graph
