"""Traffic assignment on a real street network.

Trips between random junctions of a real street network: the drivable streets of downtown
Burlington, Vermont, from OpenStreetMap (bundled, ODbL 1.0, © OpenStreetMap contributors;
see ``modelly.space.geo.samples``), one-way streets kept one-way. Every step ``trips``
travellers each draw an origin and a different destination uniformly among the junctions
and drive a shortest path by length; the model adds one vehicle to the flow of every
street segment on the way. This is all-or-nothing assignment, the assignment step of the
classic four-step transport model, with uniform demand.

All shortest paths are computed once (scipy's Dijkstra from every junction). A step is
vectorised over all origins at once: trips are counted per (origin, destination), and the
counts are pushed from each destination back to its origin along the shortest-path trees,
farthest junction first, so a step costs one pass over the junctions whatever the number
of trips. The model holds ``n x n`` arrays, so it suits networks of up to a few thousand
junctions.

Validation: the edge betweenness. A trip from ``s`` to ``t`` uses edge ``e`` exactly when
``e`` is on the shortest path from ``s`` to ``t``, so after ``T`` trips the flow on ``e`` is
binomial with mean ``T * B(e) / (n (n - 1))``, where ``B(e)`` counts the ordered pairs whose
shortest path uses ``e`` (the edge betweenness of Girvan and Newman, computed by Brandes'
algorithm). The test checks ``betweenness()`` against NetworkX's independent
implementation, and the simulated flows against the binomial law.

References:
    Brandes, U. (2001). A faster algorithm for betweenness centrality. Journal of
    Mathematical Sociology, 25(2), 163-177.

    Girvan, M. and Newman, M. E. J. (2002). Community structure in social and biological
    networks. Proceedings of the National Academy of Sciences, 99(12), 7821-7826.

    Ortuzar, J. de D. and Willumsen, L. G. (2011). Modelling Transport, 4th ed. Wiley.
"""

from __future__ import annotations

import numpy as np

from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario

NO_PREDECESSOR = -9999  # scipy's mark for "no predecessor"


class RoadTrafficScenario(Scenario):
    """Parameters of the traffic-assignment model.

    Attributes:
        trips: trips started every step.
        weight: the edge attribute shortest paths minimise (``length``, in metres).
        roads: a ``modelly.space.geo.RoadNetwork``; the bundled downtown Burlington
            streets when ``None`` (needs the ``geo`` extra).
        steps: default run length used by ``run``.
    """

    trips: int = 500
    weight: str = "length"
    roads: object = None
    steps: int = 20


class RoadTraffic(Model):
    """Random trips routed by shortest path; flows counted per street segment.

    Example:
        >>> model = RoadTraffic(RoadTrafficScenario(rng=1, steps=2))
        >>> model.run()
        >>> int(model.trips_made)
        1000
    """

    def __init__(self, scenario: RoadTrafficScenario = RoadTrafficScenario) -> None:
        """Load the streets and compute every shortest path."""
        super().__init__(scenario=scenario)
        s = self.scenario
        self.roads = _sample_roads(self) if s.roads is None else s.roads
        matrix = self.roads.routing_matrix(s.weight).tocoo()
        self.n = matrix.shape[0]
        self.tails, self.heads = matrix.row.astype(np.intp), matrix.col.astype(np.intp)
        self.distance, self.tree_edge, self.order = _shortest_path_trees(matrix)
        self.flows = np.zeros(self.tails.size)
        self.trips_made = 0
        self.trip_length = 0.0
        self.datacollector = DataCollector(
            model_reporters={
                "trips": "trips_made",
                "mean_trip_length": "trip_length",
                "max_flow": lambda m: float(m.flows.max()),
            }
        )
        self.datacollector.collect(self)

    def step(self) -> None:
        """Draw this step's trips, route them, and add them to the flows."""
        n, trips = self.n, self.scenario.trips
        origins = self.rng.integers(n, size=trips)
        destinations = (origins + self.rng.integers(1, n, size=trips)) % n
        demand = np.bincount(origins * n + destinations, minlength=n * n)
        self.flows += self.loads(demand.reshape(n, n))
        self.trips_made += trips
        self.trip_length = float(self.distance[origins, destinations].mean())
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` steps (the scenario's ``steps`` by default)."""
        self.run_for(self.scenario.steps if steps is None else steps)

    def loads(self, demand: np.ndarray) -> np.ndarray:
        """Vehicles per edge when ``demand[s, t]`` trips go from ``s`` to ``t``."""
        sources = np.arange(self.n)
        carried = demand.astype(float)
        loads = np.zeros(self.tails.size)
        for k in range(self.n - 1, 0, -1):
            node = self.order[:, k]
            edge = self.tree_edge[sources, node]
            here = carried[sources, node]
            carried[sources, self.tails[edge]] += here
            np.add.at(loads, edge, here)
        return loads

    def betweenness(self) -> np.ndarray:
        """Ordered pairs ``(s, t)`` whose shortest path uses each edge."""
        return self.loads(1 - np.eye(self.n, dtype=np.int64))

    def expected_flows(self) -> np.ndarray:
        """Mean flow per edge after the trips made so far: ``T * B(e) / (n (n - 1))``."""
        return self.trips_made * self.betweenness() / (self.n * (self.n - 1))

    def edge_labels(self) -> list[tuple]:
        """``(from, to)`` junction labels of every edge, in flow order."""
        nodes = self.roads.nodes
        return [(nodes[u], nodes[v]) for u, v in zip(self.tails, self.heads)]


def _sample_roads(model: Model):
    """The bundled downtown Burlington streets (imported here: needs the geo extra)."""
    from modelly.space.geo.samples import sample_roads  # noqa: PLC0415 - geo extra

    return sample_roads(random=model.random)


def _shortest_path_trees(matrix) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """All-pairs distances, the tree edge into every node, and nodes by distance.

    Raises:
        ValueError: if some junction cannot be reached from another.
    """
    from scipy.sparse.csgraph import dijkstra  # noqa: PLC0415 - scipy is heavy

    distance, predecessor = dijkstra(matrix.tocsr(), return_predecessors=True)
    if np.isinf(distance).any():
        raise ValueError("Every junction must be reachable from every other one.")
    n = matrix.shape[0]
    keys = matrix.row.astype(np.int64) * n + matrix.col
    sort = np.argsort(keys)
    parent = np.where(predecessor == NO_PREDECESSOR, 0, predecessor)
    wanted = parent.astype(np.int64) * n + np.arange(n)
    tree_edge = sort[np.searchsorted(keys[sort], wanted).clip(max=keys.size - 1)]
    return distance, tree_edge, np.argsort(distance, axis=1, kind="stable")
