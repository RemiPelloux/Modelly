"""Tests for the grid-block partitioner (modelly.distributed.partition)."""

from itertools import product

import numpy as np
import pytest

from modelly import Model
from modelly.distributed import grid_blocks, partition
from modelly.space import OrthogonalMooreGrid

WIDTH, HEIGHT = 10, 7


def _layout(rows=2, cols=3, torus=False, dims=(WIDTH, HEIGHT)):
    """A layout of a grid of ``dims``."""
    return grid_blocks(rows, cols).layout(dimensions=dims, torus=torus)


def test_blocks_cover_every_cell_once():
    """Each cell belongs to exactly one block."""
    layout = _layout()
    cells = [c for block in layout for c in block.cells()]
    assert sorted(cells) == sorted(product(range(WIDTH), range(HEIGHT)))
    assert len(layout) == grid_blocks(2, 3).partitions == 6


def test_cuts_are_balanced_larger_first():
    """Axis runs differ by at most one cell, the larger ones first."""
    layout = _layout(3, 2)
    widths = [b.shape[0] for b in layout.blocks[::2]]
    assert widths == [4, 3, 3]
    assert max(b.shape[1] for b in layout) - min(b.shape[1] for b in layout) <= 1


def test_owner_agrees_with_blocks_and_owner_map():
    """owner, owners and owner_map name the block that contains each cell."""
    layout = _layout()
    for block in layout:
        for cell in block.cells():
            assert cell in block
            assert layout.owner(cell) == block.index
            assert layout.owner_map[cell] == block.index
    assert not layout.owner_map.flags.writeable


def test_owners_vectorised_and_refuses_outside_cells():
    """`owners` takes an array; a coordinate off the grid is an error."""
    layout = _layout()
    coords = np.array([[0, 0], [9, 6], [5, 3]])
    assert layout.owners(coords).tolist() == [layout.owner(tuple(c)) for c in coords]
    with pytest.raises(ValueError, match="outside"):
        layout.owner((WIDTH, 0))


def test_layout_reads_a_grid():
    """A layout taken from a grid uses its dimensions and torus setting."""
    model = Model(rng=1)
    grid = OrthogonalMooreGrid((WIDTH, HEIGHT), torus=True, random=model.random)
    layout = partition.grid_blocks(2, 2).layout(grid)
    assert layout.dimensions == (WIDTH, HEIGHT)
    assert layout.torus


def _brute_halo(layout, index, radius):
    """The halo by definition: other blocks' cells within Chebyshev ``radius``."""
    width, height = layout.dimensions
    halo = set()
    for x, y in layout.blocks[index].cells():
        for dx, dy in product(range(-radius, radius + 1), repeat=2):
            nx, ny = x + dx, y + dy
            if layout.torus:
                nx, ny = nx % width, ny % height
            elif not (0 <= nx < width and 0 <= ny < height):
                continue
            if layout.owner((nx, ny)) != index:
                halo.add((nx, ny))
    return halo


@pytest.mark.parametrize("torus", [False, True])
@pytest.mark.parametrize("radius", [0, 1, 2])
def test_halo_matches_its_definition(torus, radius):
    """The halo equals the cells found by walking every neighbourhood."""
    layout = _layout(torus=torus)
    for index in range(len(layout)):
        assert layout.halo(index, radius) == _brute_halo(layout, index, radius)


def test_torus_links_opposite_edges():
    """On a torus the corner block borders the far blocks; on a plain grid it does not."""
    assert _layout(torus=True).neighbours(0) == {1, 2, 3, 4, 5}
    assert _layout(torus=False).neighbours(0) == {1, 3, 4}


def test_single_block_has_no_halo():
    """One block owns everything and needs no ghost cells."""
    layout = _layout(1, 1)
    assert layout.halo(0, 3) == frozenset()
    assert layout.neighbours(0) == frozenset()


@pytest.mark.parametrize(
    ("rows", "cols", "dims", "message"),
    [
        (0, 1, (4, 4), "at least one"),
        (5, 1, (4, 4), "cannot cut"),
        (1, 1, (4, 4, 4), "2-D"),
    ],
)
def test_impossible_splits_are_refused(rows, cols, dims, message):
    """Empty splits, more blocks than cells and 3-D grids are errors."""
    with pytest.raises(ValueError, match=message):
        grid_blocks(rows, cols).layout(dimensions=dims, torus=False)


def test_negative_radius_is_refused():
    """A halo radius is a number of steps, at least zero."""
    with pytest.raises(ValueError, match="radius"):
        _layout().halo(0, -1)
