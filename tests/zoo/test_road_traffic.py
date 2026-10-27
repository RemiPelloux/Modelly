"""Traffic assignment on real streets: flows against the exact edge betweenness."""

import numpy as np
import pytest

pytest.importorskip("geopandas")
pytest.importorskip("networkx")

import networkx as nx

from modelly.zoo.road_traffic.model import RoadTraffic, RoadTrafficScenario

SEEDS = (1, 2, 3)
# Five standard deviations of a binomial flow, over about 600 edges: no fixed seed
# should get near it.
Z_BOUND = 5.0


@pytest.fixture(scope="module")
def streets():
    """The bundled downtown Burlington streets, loaded once."""
    return RoadTraffic(RoadTrafficScenario(rng=0)).roads


def test_betweenness_matches_networkx(streets):
    """The model's shortest-path trees give NetworkX's edge betweenness, edge by edge."""
    model = RoadTraffic(RoadTrafficScenario(rng=0, roads=streets))
    reference = nx.edge_betweenness_centrality(
        streets.graph, normalized=False, weight="length"
    )
    expected = np.array([reference[edge] for edge in model.edge_labels()])
    np.testing.assert_allclose(model.betweenness(), expected)
    hops = sum(len(path) - 1 for path in _all_paths(streets.graph).values())
    assert model.betweenness().sum() == pytest.approx(hops)


def _all_paths(graph):
    """Every shortest path by length, keyed by (origin, destination)."""
    paths = dict(nx.all_pairs_dijkstra_path(graph, weight="length"))
    return {(s, t): p for s, row in paths.items() for t, p in row.items() if s != t}


@pytest.mark.parametrize("seed", SEEDS)
def test_flows_are_binomial_around_the_betweenness(seed, streets):
    """After T trips each flow is within the binomial bound of ``T B(e) / (n (n-1))``."""
    model = RoadTraffic(RoadTrafficScenario(rng=seed, roads=streets))
    model.run()
    total = model.trips_made
    assert total == model.scenario.trips * model.scenario.steps
    share = model.betweenness() / (model.n * (model.n - 1))
    used = share > 0
    sd = np.sqrt(total * share[used] * (1 - share[used]))
    z = (model.flows[used] - model.expected_flows()[used]) / sd
    assert np.abs(z).max() < Z_BOUND
    assert (model.flows[~used] == 0).all()


def test_one_way_streets_make_routes_asymmetric(streets):
    """Distances are NetworkX's; one-way streets make some trips longer than the way back."""
    model = RoadTraffic(RoadTrafficScenario(rng=4, roads=streets))
    graph = streets.graph
    origin = streets.nodes[0]
    lengths = nx.single_source_dijkstra_path_length(graph, origin, weight="length")
    row = [lengths[node] for node in streets.nodes]
    np.testing.assert_allclose(model.distance[0], row)
    assert any(not graph.has_edge(v, u) for u, v in graph.edges)
    assert not np.allclose(model.distance, model.distance.T)


def test_unreachable_junctions_are_an_error(streets):
    """A network that is not strongly connected cannot be assigned uniformly."""
    from modelly.space.geo import RoadNetwork  # noqa: PLC0415

    graph = nx.DiGraph([(0, 1)])
    for node, x in ((0, 0.0), (1, 100.0)):
        graph.nodes[node].update(x=x, y=0.0)
    roads = RoadNetwork(graph, random=streets.space.random)
    with pytest.raises(ValueError, match="reachable"):
        RoadTraffic(RoadTrafficScenario(rng=1, roads=roads))


def test_same_seed_same_flows(streets):
    """Same seed, same flows and reporters; another seed, other flows."""

    def run(seed):
        model = RoadTraffic(RoadTrafficScenario(rng=seed, roads=streets, steps=5))
        model.run()
        return model.flows, model.datacollector.get_model_vars_dataframe()

    flows, frame = run(7)
    again, frame_again = run(7)
    assert np.array_equal(flows, again) and frame.equals(frame_again)
    assert not np.array_equal(flows, run(8)[0])
