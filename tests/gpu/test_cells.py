"""DeviceCellIndex: the operators of a CellIndex, as device arrays."""

import numpy as np
import pytest

from modelly.gpu import DeviceCellIndex, PhiloxStream
from modelly.space import CellIndex, OrthogonalMooreGrid

SEED = 9


def grid_index(side=12):
    """A host index over a torus Moore grid."""
    import random  # noqa: PLC0415

    grid = OrthogonalMooreGrid((side, side), torus=True, random=random.Random(0))
    return CellIndex(grid)


def irregular_csr(cells=500, seed=0):
    """A CSR adjacency with degrees 0 to 6 (the first ten cells isolated)."""
    rng = np.random.default_rng(seed)
    degree = rng.integers(0, 7, cells)
    degree[:10] = 0
    indptr = np.concatenate([[0], np.cumsum(degree)])
    return indptr, rng.integers(0, cells, indptr[-1])


def test_counts_and_neighbor_sums_equal_the_host_index():
    """Counts and neighbor_sum give the host index's integers and floats."""
    host = grid_index()
    device = DeviceCellIndex(host)
    rows = np.random.default_rng(1).integers(0, len(host), 1_000)
    flags = rows % 3 == 0
    assert np.array_equal(device.counts(rows), host.counts(rows))
    assert np.array_equal(device.counts(rows, flags), host.counts(rows, flags))
    assert device.counts(rows, flags).dtype.kind == "i"
    values = np.random.default_rng(2).random(len(host))
    assert np.allclose(device.neighbor_sum(values), host.neighbor_sum(values))
    ints = np.arange(len(host))
    assert np.array_equal(device.neighbor_sum(ints), host.neighbor_sum(ints))


def test_random_neighbor_moves_to_a_neighbor_uniformly():
    """Every move goes to a connected cell, and each neighbour is equally likely."""
    host = grid_index()
    device = DeviceCellIndex(host)
    rows = np.full(40_000, 30)
    moved = device.random_neighbor(rows, PhiloxStream(SEED))
    neighbours = {cell.index for cell in host.cells[30].connections.values()}
    assert set(moved.tolist()) == neighbours
    counts = np.bincount(moved, minlength=len(host))[sorted(neighbours)]
    assert np.all(np.abs(counts / 5_000 - 1) < 0.08)


def test_isolated_cells_stay_and_layers_reshape():
    """A cell without neighbours keeps its agents; to_layer needs grid dimensions."""
    indptr, indices = irregular_csr()
    device = DeviceCellIndex.from_csr(indptr, indices)
    rows = np.arange(10)
    assert np.array_equal(device.random_neighbor(rows, PhiloxStream(SEED)), rows)
    with pytest.raises(ValueError):
        device.to_layer(np.zeros(len(device)))
    host = grid_index(4)
    assert DeviceCellIndex(host).to_layer(np.arange(16)).shape == (4, 4)
    assert "connections" in repr(device)


def test_an_index_without_connections_returns_the_rows():
    """No connection at all: random_neighbor is the identity."""
    device = DeviceCellIndex.from_csr(
        np.zeros(4, dtype=np.int64), np.zeros(0, dtype=np.int64)
    )
    assert device.random_neighbor(np.array([0, 2]), PhiloxStream(SEED)).tolist() == [
        0,
        2,
    ]


def test_gpu_backends_give_the_numpy_moves_and_counts(other_backend):
    """Moves, counts and integer neighbour sums are identical on the GPU backends."""
    indptr, indices = irregular_csr()
    rows = np.random.default_rng(3).integers(0, 500, 20_000)
    results = []
    for backend in (None, other_backend):
        device = DeviceCellIndex.from_csr(indptr, indices, backend)
        moved = device.random_neighbor(
            device.backend.asarray(rows), PhiloxStream(SEED, 1, backend)
        )
        counts = device.counts(moved, moved % 2 == 0)
        results.append(
            [
                device.backend.to_numpy(a)
                for a in (moved, counts, device.neighbor_sum(counts))
            ]
        )
    for mine, theirs in zip(*results):
        assert np.array_equal(mine, theirs)
