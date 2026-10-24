"""Network statistics match NetworkX on test graphs, for every input form."""

import numpy as np
import pytest

nx = pytest.importorskip("networkx")

from modelly import DataCollector, Model  # noqa: E402
from modelly.space import Network  # noqa: E402
from modelly.space.networks import (  # noqa: E402
    TemporalNetwork,
    average_clustering,
    clustering,
    component_sizes,
    degree_distribution,
    from_networkx,
    largest_component,
    mean_degree,
    network_reporter,
)

GRAPHS = {
    "karate": nx.karate_club_graph,
    "lattice": lambda: nx.convert_node_labels_to_integers(nx.grid_2d_graph(4, 5)),
    "random": lambda: nx.gnp_random_graph(60, 0.05, seed=7),
    "caveman": lambda: nx.connected_caveman_graph(4, 5),
    "pieces": lambda: nx.disjoint_union(nx.path_graph(5), nx.complete_graph(4)),
}


@pytest.mark.parametrize("name", sorted(GRAPHS))
def test_statistics_match_networkx(name):
    """Degrees, clustering and component sizes equal NetworkX's."""
    graph = GRAPHS[name]()
    assert degree_distribution(graph).tolist() == nx.degree_histogram(graph)
    expected = nx.clustering(graph)
    np.testing.assert_allclose(clustering(graph), [expected[n] for n in graph])
    assert average_clustering(graph) == pytest.approx(nx.average_clustering(graph))
    sizes = sorted((len(c) for c in nx.connected_components(graph)), reverse=True)
    assert component_sizes(graph).tolist() == sizes
    assert largest_component(graph) == sizes[0]
    assert mean_degree(graph) == pytest.approx(2 * graph.number_of_edges() / len(graph))


def test_every_input_form_agrees():
    """A NetworkX graph, a Network space, a MultilayerNetwork and a matrix agree."""
    graph = nx.karate_club_graph()
    multilayer = from_networkx(graph)
    space = Network(graph, random=Model(rng=1).random)
    matrix = nx.to_scipy_sparse_array(graph)
    for form in (multilayer, space, matrix):
        assert degree_distribution(form).tolist() == nx.degree_histogram(graph)
        assert average_clustering(form) == pytest.approx(nx.average_clustering(graph))
    empty = TemporalNetwork()
    assert component_sizes(empty).size == 0 and largest_component(empty) == 0
    assert mean_degree(empty) == 0.0 and average_clustering(empty) == 0.0


def test_reporter_collects_and_checkpoints(tmp_path):
    """network_reporter gives a DataCollector reporter that pickles."""
    model = Model(rng=1)
    model.contacts = TemporalNetwork(4, clock=model)
    model.contacts.add_edge(0, 1)
    model.contacts.add_edge(2, 3, (1, 2))
    model.datacollector = DataCollector(
        {"giant": network_reporter("contacts", largest_component)}
    )
    model.datacollector.collect(model)
    model.run_for(1)
    model.datacollector.collect(model)
    model.save(tmp_path / "collectors.ckpt")
    restored = Model.load(tmp_path / "collectors.ckpt")
    restored.datacollector.collect(restored)
    frame = restored.datacollector.get_model_vars_dataframe()
    assert frame["giant"].tolist() == [2, 2, 2]
    assert component_sizes(restored.contacts).tolist() == [2, 2]
