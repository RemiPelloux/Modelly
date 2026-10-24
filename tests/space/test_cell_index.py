"""Tests for CellIndex: rows, counts, adjacency and the vectorised random walk."""

import networkx as nx
import numpy as np

from modelly import Model
from modelly.space import (
    CellIndex,
    Network,
    OrthogonalMooreGrid,
    OrthogonalVonNeumannGrid,
)


def test_rows_follow_the_grid_coordinate_order():
    """cell.index is the C-order flat index of the coordinate, so to_layer is a layer."""
    model = Model(rng=1)
    grid = OrthogonalMooreGrid((4, 3), torus=False, random=model.random)
    index = CellIndex(grid)
    assert len(index) == 12
    for cell in grid.all_cells:
        x, y = cell.coordinate
        assert cell.index == x * 3 + y
    layer = index.to_layer(np.arange(12))
    assert layer.shape == (4, 3)
    assert layer[2, 1] == grid[(2, 1)].index


def test_counts_and_rows():
    """counts() is a bincount over the whole space, with optional weights."""
    model = Model(rng=1)
    grid = OrthogonalVonNeumannGrid((3, 3), random=model.random)
    index = CellIndex(grid)
    rows = index.rows([grid[(0, 0)], grid[(0, 0)], grid[(2, 2)]])
    assert rows.tolist() == [0, 0, 8]
    assert index.counts(rows).tolist() == [2, 0, 0, 0, 0, 0, 0, 0, 1]
    weighted = index.counts(rows, weights=np.array([1.0, 0.0, 3.0]))
    assert weighted[0] == 1.0 and weighted[8] == 3.0


def test_adjacency_matches_the_cell_connections():
    """The CSR matrix has one entry per connection, on grids and networks alike."""
    model = Model(rng=1)
    grid = OrthogonalMooreGrid((5, 5), torus=True, random=model.random)
    index = CellIndex(grid)
    adjacency = index.adjacency
    assert adjacency.shape == (25, 25)
    assert adjacency.nnz == 25 * 8
    ones = np.ones(25)
    assert index.neighbor_sum(ones).tolist() == [8.0] * 25

    graph = nx.path_graph(4)
    network = Network(graph, random=model.random)
    net_index = CellIndex(network)
    degrees = net_index.neighbor_sum(np.ones(4))
    assert degrees.tolist() == [1.0, 2.0, 2.0, 1.0]
    values = np.array([1.0, 10.0, 100.0, 1000.0])
    assert net_index.neighbor_sum(values).tolist() == [10.0, 101.0, 1010.0, 100.0]


def test_random_neighbor_stays_on_the_connections():
    """random_neighbor picks a connected row; isolated rows stay put."""
    model = Model(rng=3)
    grid = OrthogonalVonNeumannGrid((6, 6), torus=True, random=model.random)
    index = CellIndex(grid)
    rows = np.arange(36)
    chosen = index.random_neighbor(rows, model.rng)
    for row, new in zip(rows, chosen):
        assert index.cells[new] in index.cells[row].connections.values()

    graph = nx.Graph()
    graph.add_nodes_from([0, 1])
    lonely = CellIndex(Network(graph, random=model.random))
    assert lonely.random_neighbor(np.array([0, 1]), model.rng).tolist() == [0, 1]
