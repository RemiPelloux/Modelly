"""Road networks: a NetworkX graph with node coordinates as a ``Network`` space, and routing.

Nodes carry their coordinates as ``x`` and ``y`` attributes (the OSMnx convention) and
edges a ``length``; edges without one get the straight-line length between their ends.
The graph is reprojected once into the network's CRS. Agents can stand on its nodes as
``CellAgent``s of ``space``, and route with NetworkX (one pair) or scipy (many sources).
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING, Any

import numpy as np
import pyproj
import shapely

from modelly.space.geo._deps import require
from modelly.space.network import Network

if TYPE_CHECKING:
    from scipy.sparse import csr_matrix

    from modelly.core.agent import Agent
    from modelly.space.geo.space import GeoSpace

LENGTH = "length"
TRAVEL_TIME = "travel_time"
SPEED = "speed"


class RoadNetwork:
    """A road graph in one projected CRS, its ``Network`` space and shortest paths.

    Attributes:
        graph: the NetworkX graph (any of Graph, DiGraph, MultiGraph, MultiDiGraph).
        crs: the ``pyproj.CRS`` of the node coordinates, or ``None``.
        space: a ``Network`` space with one cell per node, at the node's coordinates.
        weight: the default edge attribute for routing.
    """

    def __init__(
        self,
        graph: Any,
        crs: Any = None,
        random: Random | None = None,
        weight: str = LENGTH,
    ) -> None:
        """Wrap ``graph``; its own CRS is ``graph.graph["crs"]``, as OSMnx sets it.

        Args:
            graph: a NetworkX graph whose nodes have ``x`` and ``y`` attributes.
            crs: the CRS to route in; defaults to the graph's, or its UTM zone if geographic.
            random: a seeded ``random.Random`` for the ``Network`` space.
            weight: the default edge attribute shortest paths minimise.
        """
        source = graph.graph.get("crs")
        self.crs = _target_crs(graph, source, crs)
        if source is not None and self.crs is not None:
            graph = _reproject_graph(
                graph, pyproj.CRS.from_user_input(source), self.crs
            )
        _fill_lengths(graph)
        self.graph = graph
        self.weight = weight
        self.nodes = list(graph.nodes)
        self._row = {node: i for i, node in enumerate(self.nodes)}
        layout = {n: (d["x"], d["y"]) for n, d in graph.nodes(data=True)}
        self.space = Network(graph, random=random, layout=layout)
        self._csr_cache: dict[str, csr_matrix] = {}

    def __getstate__(self) -> dict:
        """Drop the routing matrices; they are rebuilt on first use after a load."""
        state = self.__dict__.copy()
        state["_csr_cache"] = {}
        return state

    def node_of(self, point: Any) -> Any:
        """``point`` itself if it is a node, else the node nearest to it (``Point`` or ``(x, y)``)."""
        try:
            if point in self._row:
                return point
        except TypeError:
            pass
        if isinstance(point, shapely.Point):
            point = (point.x, point.y)
        return self.space.find_nearest_cell(np.asarray(point, dtype=float)).coordinate

    def nearest_nodes(self, xy: np.ndarray) -> np.ndarray:
        """Row (position in ``nodes``) of the node nearest to every point of ``xy``."""
        if self.space._kdtree_dirty:
            self.space._rebuild_kdtree()
        _, rows = self.space._kdtree.query(np.atleast_2d(xy))
        cells = self.space._kdtree_cells
        return np.fromiter(
            (self._row[cells[r].coordinate] for r in rows), dtype=np.intp
        )

    def shortest_path(
        self, origin: Any, destination: Any, weight: str | None = None
    ) -> list:
        """The nodes of a shortest path; ``origin`` and ``destination`` are nodes or points."""
        import networkx as nx  # noqa: PLC0415

        return nx.shortest_path(
            self.graph,
            self.node_of(origin),
            self.node_of(destination),
            weight=weight or self.weight,
        )

    def path_length(
        self, origin: Any, destination: Any, weight: str | None = None
    ) -> float:
        """The total ``weight`` of a shortest path between two nodes or points."""
        import networkx as nx  # noqa: PLC0415

        return float(
            nx.shortest_path_length(
                self.graph,
                self.node_of(origin),
                self.node_of(destination),
                weight=weight or self.weight,
            )
        )

    def travel_time(self, origin: Any, destination: Any) -> float:
        """The shortest travel time between two nodes or points (see ``add_travel_times``)."""
        return self.path_length(origin, destination, weight=TRAVEL_TIME)

    def add_travel_times(self, speed: float) -> None:
        """Set ``travel_time = length / speed`` on every edge.

        Args:
            speed: in CRS units per unit of model time, for edges without a ``speed``
                attribute of their own.
        """
        for _, _, data in self.graph.edges(data=True):
            data[TRAVEL_TIME] = data[LENGTH] / data.get(SPEED, speed)
        self.invalidate(TRAVEL_TIME)

    def distances_from(
        self, origin: Any, cutoff: float | None = None, weight: str | None = None
    ) -> dict:
        """Shortest ``weight`` from ``origin`` to every node reachable within ``cutoff``."""
        import networkx as nx  # noqa: PLC0415

        return nx.single_source_dijkstra_path_length(
            self.graph,
            self.node_of(origin),
            cutoff=cutoff,
            weight=weight or self.weight,
        )

    def distance_matrix(self, origins: Any, weight: str | None = None) -> np.ndarray:
        """Shortest ``weight`` from every origin (nodes or points) to every node, with scipy.

        Returns:
            an array of shape ``(len(origins), len(nodes))``; unreachable nodes are ``inf``.
        """
        from scipy.sparse.csgraph import dijkstra  # noqa: PLC0415 - scipy is heavy

        rows = [self._row[self.node_of(origin)] for origin in origins]
        return dijkstra(self.routing_matrix(weight), directed=True, indices=rows)

    def routing_matrix(self, weight: str | None = None) -> csr_matrix:
        """The graph as a CSR matrix of ``weight``, rows in ``nodes`` order.

        Parallel edges keep the smallest weight; an undirected edge counts both ways.
        """
        weight = weight or self.weight
        if weight not in self._csr_cache:
            self._csr_cache[weight] = _routing_matrix(self, weight)
        return self._csr_cache[weight]

    def invalidate(self, weight: str | None = None) -> None:
        """Forget the routing matrix of ``weight`` (all when ``None``) after edges changed."""
        if weight is None:
            self._csr_cache.clear()
        else:
            self._csr_cache.pop(weight, None)

    def path_geometry(self, path: list) -> shapely.LineString:
        """The polyline through the coordinates of the nodes of ``path``."""
        nodes = self.graph.nodes
        return shapely.LineString([(nodes[n]["x"], nodes[n]["y"]) for n in path])

    def agents_within(
        self, space: GeoSpace, origin: Any, distance: float, weight: str | None = None
    ) -> list[Agent]:
        """The agents of ``space`` whose nearest node is within network ``distance`` of ``origin``."""
        reached = self.distances_from(origin, cutoff=distance, weight=weight)
        mask = np.zeros(len(self.nodes), dtype=bool)
        mask[[self._row[node] for node in reached]] = True
        near = mask[self.nearest_nodes(space.agent_positions)]
        return [space.active_agents[i] for i in np.flatnonzero(near)]


def download_osm(
    place: str,
    network_type: str = "drive",
    crs: Any = None,
    random: Random | None = None,
) -> RoadNetwork:
    """Download the road network of ``place`` from OpenStreetMap (needs the ``osm`` extra).

    Edges get OSMnx's ``speed_kph`` and ``travel_time`` (seconds) attributes. This makes a
    network request: cache the result (``osmnx.save_graphml``) rather than calling it per run.
    """
    ox = require("osmnx", "osm")
    graph = ox.graph_from_place(place, network_type=network_type)
    graph = ox.add_edge_travel_times(ox.add_edge_speeds(graph))
    return RoadNetwork(graph, crs=crs, random=random)


def _target_crs(graph: Any, source: Any, crs: Any) -> pyproj.CRS | None:
    """The CRS asked for, else the graph's, replaced by its UTM zone when geographic."""
    if crs is not None:
        return pyproj.CRS.from_user_input(crs)
    if source is None:
        return None
    source = pyproj.CRS.from_user_input(source)
    if not source.is_geographic:
        return source
    import geopandas as gpd  # noqa: PLC0415

    xy = np.array([(d["x"], d["y"]) for _, d in graph.nodes(data=True)])
    return gpd.GeoSeries(shapely.points(xy), crs=source).estimate_utm_crs()


def _reproject_graph(graph: Any, source: pyproj.CRS, target: pyproj.CRS) -> Any:
    """A copy of ``graph`` with node coordinates and edge geometries in ``target``."""
    if source == target:
        return graph
    transformer = pyproj.Transformer.from_crs(source, target, always_xy=True)
    graph = graph.copy()
    for _, data in graph.nodes(data=True):
        data["x"], data["y"] = transformer.transform(data["x"], data["y"])
    for _, _, data in graph.edges(data=True):
        if "geometry" in data:
            data["geometry"] = shapely.transform(
                data["geometry"],
                lambda xy: np.column_stack(transformer.transform(*xy.T)),
            )
    graph.graph["crs"] = target.to_wkt()
    return graph


def _fill_lengths(graph: Any) -> None:
    """Give every edge without a ``length`` the straight-line length between its ends."""
    nodes = graph.nodes
    for u, v, data in graph.edges(data=True):
        if LENGTH not in data:
            dx = nodes[u]["x"] - nodes[v]["x"]
            dy = nodes[u]["y"] - nodes[v]["y"]
            data[LENGTH] = float(np.hypot(dx, dy))


def _routing_matrix(roads: RoadNetwork, weight: str) -> csr_matrix:
    """The smallest ``weight`` per directed node pair, as a CSR matrix."""
    from scipy.sparse import csr_matrix  # noqa: PLC0415 - scipy is heavy

    best: dict[tuple[int, int], float] = {}
    row = roads._row
    both_ways = not roads.graph.is_directed()
    for u, v, data in roads.graph.edges(data=True):
        pairs = (
            ((row[u], row[v]), (row[v], row[u])) if both_ways else ((row[u], row[v]),)
        )
        for pair in pairs:
            best[pair] = min(best.get(pair, np.inf), float(data[weight]))
    n = len(roads.nodes)
    if not best:
        return csr_matrix((n, n))
    pairs = np.array(list(best), dtype=np.intp)
    weights = np.fromiter(best.values(), dtype=float, count=len(best))
    return csr_matrix((weights, (pairs[:, 0], pairs[:, 1])), shape=(n, n))
