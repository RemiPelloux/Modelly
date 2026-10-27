"""Tests for the graph partitioner (modelly.distributed.graphs)."""

import networkx as nx
import numpy as np
import pytest

from modelly.distributed import partition
from modelly.distributed.graphs import banded_order, neighbours_of


def _layout(graph, parts=4):
    """The layout of ``graph`` in ``parts`` parts."""
    return partition.graph(parts).layout(graph)


def test_every_node_has_one_part_and_parts_are_balanced():
    """Parts cover the nodes and stay within the imbalance of their target size."""
    graph = nx.grid_2d_graph(20, 15)
    layout = _layout(graph, 6)
    sizes = layout.sizes()
    assert sizes.sum() == graph.number_of_nodes()
    target = graph.number_of_nodes() / 6
    assert sizes.max() <= np.ceil(target * (1 + partition.graph(6).imbalance))
    assert len(layout) == 6


def test_layout_is_deterministic():
    """The same graph gives the same parts on every call."""
    graph = nx.watts_strogatz_graph(500, 6, 0.1, seed=3)
    first, second = _layout(graph), _layout(graph)
    assert np.array_equal(first.assignment, second.assignment)


def test_cut_far_below_a_random_split():
    """On a lattice, the cut is a fraction of a random assignment's (and near 2x optimal)."""
    graph = nx.grid_2d_graph(30, 30)
    layout = _layout(graph, 4)
    random_parts = np.random.default_rng(0).integers(0, 4, graph.number_of_nodes())
    random_layout = type(layout)(
        layout.nodes, random_parts, layout._indptr, layout._indices
    )
    assert layout.cut() < random_layout.cut() / 5
    optimal = 2 * 30  # two straight cuts across the lattice
    assert layout.cut() <= 3 * optimal


def test_refinement_does_not_increase_the_cut():
    """Boundary passes only make moves that reduce the cut."""
    graph = nx.random_geometric_graph(400, 0.08, seed=2)
    refined = partition.graph(4).layout(graph)
    plain = partition.graph(4)
    unrefined = type(plain)(4, plain.imbalance, passes=0).layout(graph)
    assert refined.cut() <= unrefined.cut()


def test_halo_matches_networkx_ego_graphs():
    """The halo is every node of another part within ``radius`` hops of the part."""
    graph = nx.watts_strogatz_graph(200, 4, 0.2, seed=5)
    layout = _layout(graph, 4)
    for radius in (1, 2):
        for index in range(4):
            own = [n for n in graph.nodes if layout.owner(n) == index]
            reach = set()
            for node in own:
                reach |= set(nx.ego_graph(graph, node, radius=radius).nodes)
            assert layout.halo(index, radius) == reach - set(own)
    assert layout.halo(0, 0) == frozenset()


def test_neighbours_are_symmetric():
    """Part a sees part b in its halo exactly when b sees a."""
    layout = _layout(nx.watts_strogatz_graph(300, 6, 0.05, seed=1), 5)
    for a in range(5):
        for b in layout.neighbours(a):
            assert a in layout.neighbours(b)


def test_owners_and_owner_agree_on_any_node_labels():
    """String labels work; owners is owner applied to many nodes."""
    graph = nx.relabel_nodes(nx.path_graph(12), {i: f"n{i}" for i in range(12)})
    layout = _layout(graph, 3)
    nodes = list(graph.nodes)
    assert layout.owners(nodes).tolist() == [layout.owner(n) for n in nodes]
    assert layout.cut() == 2


def test_banded_order_covers_every_component():
    """Isolated nodes and separate components all appear once."""
    graph = nx.disjoint_union(nx.path_graph(5), nx.empty_graph(3))
    layout = _layout(graph, 2)
    indptr, indices = layout._indptr, layout._indices
    assert sorted(banded_order(indptr, indices)) == list(range(8))


def test_neighbours_of_concatenates_rows():
    """neighbours_of lists the CSR rows of the given nodes, in order."""
    indptr = np.array([0, 2, 3, 5])
    indices = np.array([1, 2, 0, 0, 1])
    assert neighbours_of(indptr, indices, np.array([2, 0])).tolist() == [0, 1, 1, 2]


def test_bad_arguments_are_refused():
    """Too many parts, no parts, negative imbalance and radius raise."""
    with pytest.raises(ValueError, match="cannot split"):
        _layout(nx.path_graph(3), 4)
    with pytest.raises(ValueError, match="at least one"):
        partition.graph(0)
    with pytest.raises(ValueError, match="imbalance"):
        partition.graph(2, imbalance=-1)
    with pytest.raises(ValueError, match="radius"):
        _layout(nx.path_graph(6), 2).halo(0, -1)
