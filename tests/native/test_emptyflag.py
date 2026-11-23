"""``cell.empty`` on a grid in C (EmptyFlag) does what its Python property does."""

import sys

import numpy as np
import pytest

from modelly import Model
from modelly._native import cells
from modelly.space import CellAgent, OrthogonalMooreGrid
from modelly.space.grid.layers import _empty_accessor

pytestmark = pytest.mark.skipif(not cells.NATIVE, reason="fastcell is not built")
STEPS = 300


def walk(indexed: bool):
    """Agents walking a small grid, optionally with the empties index; what it leaves."""
    model = Model(rng=5)
    grid = OrthogonalMooreGrid((6, 6), torus=True, random=model.random)
    if indexed:
        grid._empties.build(grid.all_cells.cells)
    agents = [CellAgent(model) for _ in range(12)]
    for agent in agents:
        agent.cell = grid.select_random_empty_cell()
    for _ in range(STEPS):
        agent = model.random.choice(agents)
        agent.cell = agent.cell.neighborhood.select_random_cell()
    empties = sorted(c.coordinate for c in grid._empties._cells)
    return grid.property_layers["empty"].tolist(), empties, type(grid._celllist[0])


def test_a_grid_installs_the_compiled_flag():
    """Grid cells get EmptyFlag, which documents itself as the property did."""
    grid = OrthogonalMooreGrid((3, 3), random=Model(rng=1).random)
    flag = type(grid._celllist[0]).__dict__["empty"]
    assert type(flag) is cells.EmptyFlag
    assert flag.__doc__ == "property_layer 'empty'"


@pytest.mark.parametrize("indexed", [False, True])
def test_walks_match_the_python_property(indexed, monkeypatch):
    """The same walk leaves the same layer and the same index of empty cells."""
    *compiled, in_c = walk(indexed)
    monkeypatch.setattr("modelly.space.grid.layers.EmptyFlag", None)
    *python, in_python = walk(indexed)  # the grid now installs the Python property
    assert type(in_c.__dict__["empty"]) is cells.EmptyFlag
    assert type(in_python.__dict__["empty"]) is property
    assert compiled == python


def test_reads_and_writes_the_layer_as_python_bools():
    """A read is a bool; a write takes any truth value and reaches the layer."""
    grid = OrthogonalMooreGrid((3, 4), random=Model(rng=1).random)
    cell, layer = grid._cells[(2, 3)], grid.property_layers["empty"]
    assert cell.empty is True
    cell.empty = 0
    assert cell.empty is False
    assert not layer[2, 3]
    cell.empty = "yes"
    assert layer[2, 3]


def test_other_coordinates_and_deletes_go_to_the_property():
    """A coordinate it cannot index, or a delete, behaves as the property would."""
    grid = OrthogonalMooreGrid((3, 3), random=Model(rng=1).random)
    cell = grid._cells[(1, 1)]
    cell.coordinate = (
        np.int64(1),
        np.int64(2),
    )  # numpy ints: the property indexes them
    cell.empty = False
    assert not grid.property_layers["empty"][1, 2]
    assert cell.empty is False
    cell.coordinate = (7, 0)
    with pytest.raises(IndexError):
        cell.empty = True
    with pytest.raises(AttributeError):
        del cell.empty


def test_rejects_what_it_cannot_back():
    """Only a writable bool array, with a data descriptor to fall back on."""
    accessor = property(lambda c: True, lambda c, v: None)
    with pytest.raises(TypeError):
        cells.EmptyFlag(np.ones(3, dtype=np.int8), accessor)
    with pytest.raises(TypeError):
        cells.EmptyFlag(np.ones(3, dtype=bool), object())
    frozen = np.ones(3, dtype=bool)
    frozen.flags.writeable = False
    with pytest.raises(ValueError, match="read-only"):
        cells.EmptyFlag(frozen, accessor)


def test_no_reference_leaks():
    """Reads and writes leave the cell, coordinate and layer counts unchanged."""
    grid = OrthogonalMooreGrid((3, 3), random=Model(rng=1).random)
    grid._empties.build(grid.all_cells.cells)
    cell, layer = grid._cells[(0, 1)], grid.property_layers["empty"]
    tracked = [cell, cell.coordinate, layer]
    before = [sys.getrefcount(x) for x in tracked]
    for _ in range(100):
        cell.empty = False
        cell.empty = True
        assert cell.empty
    assert [sys.getrefcount(x) for x in tracked] == before


def test_a_read_only_layer_keeps_the_python_property():
    """The grid falls back to the property when the layer refuses a writable buffer."""
    frozen = np.ones((2, 2), dtype=bool)
    frozen.flags.writeable = False
    assert isinstance(_empty_accessor(frozen), property)
