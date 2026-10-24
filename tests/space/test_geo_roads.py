"""RoadNetwork: Network space from a graph with coordinates, routing and travel times."""

import numpy as np
import pytest

pytest.importorskip("geopandas")
nx = pytest.importorskip("networkx")

from modelly import Model  # noqa: E402
from modelly.space import CellAgent  # noqa: E402
from modelly.space.geo import GeoAgent, GeoSpace, RoadNetwork  # noqa: E402

SPEED = 10.0  # metres per unit of model time


def test_network_space_and_lengths(grid_roads):
    """Every node is a cell at its coordinates; missing lengths are filled in."""
    model = Model(rng=1)
    roads = RoadNetwork(grid_roads, random=model.random)
    assert roads.crs.to_epsg() == 32631
    assert len(roads.space.all_cells) == 9
    assert roads.graph.edges[(0, 0), (1, 0)]["length"] == 100.0
    agent = CellAgent(model)
    agent.cell = roads.space[(1, 1)]
    assert {c.coordinate for c in agent.cell.neighborhood} == {
        (0, 1),
        (2, 1),
        (1, 0),
        (1, 2),
    }
    assert roads.node_of((240.0, 260.0)) == (2, 2)
    assert roads.node_of((1, 1)) == (1, 1)


def test_shortest_paths_and_travel_times(grid_roads):
    """Routing agrees between NetworkX and the scipy distance matrix."""
    roads = RoadNetwork(grid_roads, random=Model(rng=1).random)
    path = roads.shortest_path((0, 0), (2, 2))
    assert path[0] == (0, 0) and path[-1] == (2, 2) and len(path) == 5
    assert roads.path_length((10.0, 10.0), (290.0, 290.0)) == 400.0
    roads.add_travel_times(SPEED)
    assert roads.travel_time((0, 0), (2, 2)) == 40.0
    matrix = roads.distance_matrix([(0, 0), (1, 1)])
    expected = [roads.distances_from((0, 0))[n] for n in roads.nodes]
    np.testing.assert_allclose(matrix[0], expected)
    assert roads.distance_matrix([(0, 0)], weight="travel_time")[0].max() == 40.0
    assert roads.path_geometry(path).length == 400.0
    assert set(roads.distances_from((0, 0), cutoff=100.0)) == {(0, 0), (1, 0), (0, 1)}


def test_parallel_and_directed_edges():
    """A multigraph keeps the shortest parallel edge; one-way streets are one way."""
    graph = nx.MultiDiGraph()
    for node, x in ((0, 0.0), (1, 10.0)):
        graph.add_node(node, x=x, y=0.0)
    graph.add_edge(0, 1, length=30.0)
    graph.add_edge(0, 1, length=12.0)
    roads = RoadNetwork(graph, random=Model(rng=1).random)
    matrix = roads.distance_matrix([0, 1])
    assert matrix[0, 1] == 12.0 and np.isinf(matrix[1, 0])
    assert roads.path_length(0, 1) == 12.0


def test_reprojects_graph_coordinates(grid_roads):
    """A graph given in another CRS is reprojected into the requested one."""
    roads = RoadNetwork(grid_roads, crs="EPSG:3857", random=Model(rng=1).random)
    assert roads.crs.to_epsg() == 3857
    assert grid_roads.nodes[(0, 0)]["x"] == 50.0  # the input graph is untouched
    assert roads.graph.nodes[(0, 0)]["x"] != 50.0


def test_agents_within_network_distance(grid_roads, city_regions):
    """Agents count as near when their nearest node is within the network distance."""
    model = Model(rng=1)
    space = GeoSpace(city_regions, random=model.random)
    roads = RoadNetwork(grid_roads, random=model.random)
    for point in city_regions.geometry.centroid:
        GeoAgent(space, model, point)
    near = roads.agents_within(space, (0, 0), 100.0)
    assert sorted(a.region for a in near) == ["r0", "r1", "r3"]
    assert len(roads.nearest_nodes(space.agent_positions)) == 9
