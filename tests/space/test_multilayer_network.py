"""MultilayerNetwork and contact matrices."""

import numpy as np
import pytest

from modelly.space.networks import (
    MultilayerNetwork,
    age_groups,
    contact_matrix,
)


def three_layers():
    """Six people: two households, one school class, one workplace."""
    network = MultilayerNetwork(6, {"household": 1.0, "school": 0.5, "work": 0.25})
    network.add_edges([(0, 1), (0, 2), (1, 2), (3, 4), (3, 5), (4, 5)], "household")
    network.add_edges([(2, 5)], "school")
    network.add_edges([(0, 3), (1, 4)], "work", weight=2.0)
    return network


def test_neighbours_per_layer_and_combined():
    """Queries take one layer, several, or all, combined with layer weights."""
    network = three_layers()
    assert network.layers == ["household", "school", "work"]
    assert sorted(network.neighbors(2, "household")) == [0, 1]
    assert network.neighbors(2, "school") == [5]
    assert sorted(network.neighbors(0)) == [1, 2, 3]
    assert network.weighted_neighbors(0, ["household", "work"]) == {
        1: 1.0,
        2: 1.0,
        3: 0.5,
    }
    assert network.degree(5) == 3 and network.degree(5, "work") == 0
    assert network.has_edge(0, 3) and not network.has_edge(0, 3, "household")
    assert network.number_of_edges() == 9
    with pytest.raises(KeyError):
        network.neighbors(0, "church")


def test_adjacency_is_weighted_and_follows_changes():
    """The combined matrix is the weighted sum of the layers and tracks edits."""
    network = three_layers()
    matrix = network.adjacency()
    assert matrix[0, 3] == 0.5 and matrix[2, 5] == 0.5 and matrix[0, 1] == 1.0
    assert (matrix != matrix.T).nnz == 0
    network.remove_edge(2, 5, "school")
    network.add_edge(0, 5, "school", weight=4.0)
    updated = network.adjacency("school")
    assert updated[2, 5] == 0 and updated[5, 0] == 2.0
    network.add_layer("school", 1.0)
    assert network.adjacency("school")[0, 5] == 4.0
    with pytest.raises(KeyError):
        network.remove_edge(2, 5, "school")
    vector = np.arange(6.0)
    np.testing.assert_allclose(
        network.adjacency() @ vector, matrix_sum(network, vector)
    )


def matrix_sum(network, values):
    """Per-node weighted neighbour sum computed through the dictionary queries."""
    return np.array(
        [
            sum(w * values[j] for j, w in network.weighted_neighbors(i).items())
            for i in network.nodes
        ]
    )


def test_labels_new_nodes_and_directed():
    """Arbitrary labels, nodes added by edges, and one-way layers."""
    network = MultilayerNetwork(["ann", "bob"], ["follows"], directed=True)
    network.add_edge("ann", "bob", "follows")
    network.add_edge("bob", "cy", "follows")
    assert network.nodes == ["ann", "bob", "cy"] and len(network) == 3
    assert network.neighbors("bob") == ["cy"] and network.neighbors("cy") == []
    assert network.adjacency().shape == (3, 3)
    graph = network.to_networkx()
    assert graph.is_directed() and graph.has_edge("ann", "bob")
    with pytest.raises(ValueError):
        MultilayerNetwork(["a", "a"])


def test_contact_matrix_by_age_group():
    """Mean contacts per person between age groups, and reciprocity."""
    network = three_layers()
    ages = [40, 38, 9, 70, 45, 12]
    groups = age_groups(ages, [18, 65])
    assert groups.tolist() == [1, 1, 0, 2, 1, 0]
    household = contact_matrix(network, groups, layer="household")
    sizes = np.bincount(groups)
    np.testing.assert_allclose(
        sizes[:, None] * household, (sizes[:, None] * household).T
    )
    assert household[0, 0] == 0.0  # the two children live apart
    assert household[0, 1] == 1.5  # each child lives with 2, 1 adults
    combined = contact_matrix(network, groups, n_groups=4)
    assert combined.shape == (4, 4) and combined[3].sum() == 0
    assert combined[0, 0] == 0.5  # the school edge, layer weight 0.5
    np.testing.assert_allclose(
        contact_matrix(network.adjacency(), groups), combined[:3, :3]
    )
