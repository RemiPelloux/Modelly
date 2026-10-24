"""Small synthetic maps for the geospatial tests: no files, no network."""

import pytest

CELL = 100.0  # metres per region side and per road segment
SIDE = 3  # regions and road nodes per side
UTM = "EPSG:32631"  # UTM zone 31N, a projected CRS in metres


@pytest.fixture
def city_regions():
    """A 3 x 3 block of 100 m square regions labelled r0..r8, row by row from the south."""
    gpd = pytest.importorskip("geopandas")
    shapely = pytest.importorskip("shapely")
    boxes = [
        shapely.box(i * CELL, j * CELL, (i + 1) * CELL, (j + 1) * CELL)
        for j in range(SIDE)
        for i in range(SIDE)
    ]
    labels = [f"r{k}" for k in range(SIDE * SIDE)]
    return gpd.GeoDataFrame({"name": labels}, geometry=boxes, crs=UTM).set_index("name")


@pytest.fixture
def grid_roads():
    """A 3 x 3 lattice of roads through the region centres, nodes ``(i, j)``."""
    nx = pytest.importorskip("networkx")
    graph = nx.grid_2d_graph(SIDE, SIDE)
    for node in graph.nodes:
        graph.nodes[node]["x"] = node[0] * CELL + CELL / 2
        graph.nodes[node]["y"] = node[1] * CELL + CELL / 2
    graph.graph["crs"] = UTM
    return graph
