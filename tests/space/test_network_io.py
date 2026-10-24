"""Network import and export: NetworkX, igraph, edge-list CSV."""

import pytest

from modelly.space.networks import (
    MultilayerNetwork,
    from_igraph,
    from_networkx,
    read_edge_list,
    read_temporal_edge_list,
    write_edge_list,
)


def test_from_networkx_with_layers_and_weights():
    """Edge attributes name the layer and the weight."""
    nx = pytest.importorskip("networkx")
    graph = nx.Graph()
    graph.add_edge("a", "b", layer="home", weight=2.0)
    graph.add_edge("b", "c", layer="work")
    graph.add_edge("c", "d")
    graph.add_node("e")
    network = from_networkx(graph, layer_attribute="layer")
    assert network.layers == ["home", "work", "default"]
    assert network.weighted_neighbors("b") == {"a": 2.0, "c": 1.0}
    assert network.neighbors("e") == []
    assert from_networkx(nx.DiGraph([(1, 2)])).directed
    assert from_networkx(graph).layers == ["default"]


def test_from_igraph_when_installed():
    """Graphs from igraph import with names, layers and weights (skipped without igraph)."""
    ig = pytest.importorskip("igraph")
    graph = ig.Graph([(0, 1), (1, 2)])
    graph.vs["name"] = ["a", "b", "c"]
    graph.es["layer"] = ["home", "work"]
    graph.es["weight"] = [2.0, 3.0]
    network = from_igraph(graph, layer_attribute="layer")
    assert network.weighted_neighbors("b") == {"a": 2.0, "c": 3.0}
    assert network.layers == ["home", "work"]


def test_edge_list_round_trip(tmp_path):
    """Writing then reading a CSV keeps layers, weights and non-ASCII labels."""
    network = MultilayerNetwork(["Zoë", "José", "Ŝam"], ["home", "work"])
    network.add_edge("Zoë", "José", "home", weight=1.5)
    network.add_edge("José", "Ŝam", "work")
    path = write_edge_list(network, tmp_path / "edges.csv")
    assert (
        path.read_text(encoding="utf-8").splitlines()[0] == "source,target,layer,weight"
    )
    back = read_edge_list(path)
    assert back.layers == ["home", "work"]
    assert back.weighted_neighbors("José") == {"Zoë": 1.5, "Ŝam": 1.0}


def test_edge_list_optional_columns_and_errors(tmp_path):
    """A plain source,target file goes to the default layer; missing columns fail."""
    path = tmp_path / "plain.csv"
    path.write_text("source,target\n1,2\n2,3\n", encoding="utf-8")
    network = read_edge_list(path, directed=True)
    assert network.layers == ["default"] and network.neighbors("2") == ["3"]
    bad = tmp_path / "bad.csv"
    bad.write_text("from,to\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_edge_list(bad)


def test_temporal_edge_list(tmp_path):
    """The start and end columns give edge lifetimes; an empty end never ends."""
    path = tmp_path / "contacts.csv"
    path.write_text(
        "source,target,start,end,weight\na,b,0,2,1\nb,c,1,,0.5\n", encoding="utf-8"
    )
    network = read_temporal_edge_list(path)
    network.advance_to(1)
    assert network.weighted_neighbors("b") == {"a": 1.0, "c": 0.5}
    network.advance_to(5)
    assert network.neighbors("b") == ["c"]
