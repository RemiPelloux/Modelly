"""The compiled cell move gives exactly what its Python twin gives."""

import sys

import numpy as np
import pytest

from modelly import Model
from modelly._native import cells
from modelly.core.exceptions import AgentMissingException, CellFullException
from modelly.space import CellAgent, OrthogonalMooreGrid
from modelly.space.cells.cell import Cell

pytestmark = pytest.mark.skipif(not cells.NATIVE, reason="fastcell is not built")
fastcell = cells._fastcell
MOVERS = {"python": cells.py_set_cell, "c": fastcell.set_cell if cells.NATIVE else None}


def world(capacity=None):
    """A small torus grid (``empty`` backed by its property layer) and five agents."""
    model = Model(rng=3)
    grid = OrthogonalMooreGrid((4, 4), torus=True, random=model.random)
    for cell in grid.all_cells:
        cell.capacity = capacity  # any number type, not only what the grid validates
    return model, grid, [CellAgent(model) for _ in range(5)]


def snapshot(grid, agents):
    """Everything a move can change, by coordinate and agent position."""
    index = {a: i for i, a in enumerate(agents)}
    occupancy = {c.coordinate: [index[a] for a in c._agents] for c in grid.all_cells}
    where = [a._modelly_cell.coordinate if a._modelly_cell else None for a in agents]
    return occupancy, where, grid.property_layers["empty"].tolist()


def test_the_compiled_setter_is_installed():
    """HasCell.cell moves through the C function."""
    assert CellAgent.cell.fset is fastcell.set_cell


def test_random_walk_matches_python():
    """The same sequence of moves leaves the same lists, cells and empty layer."""
    results = []
    for move in MOVERS.values():
        _, grid, agents = world()
        cell_list = list(grid.all_cells)
        rng = np.random.default_rng(11)
        for _ in range(400):
            agent = agents[rng.integers(len(agents))]
            target = (
                None if rng.random() < 0.1 else cell_list[rng.integers(len(cell_list))]
            )
            move(agent, target)
        results.append(snapshot(grid, agents))
    assert results[0] == results[1]


@pytest.mark.parametrize("capacity", [1, np.int64(1), 1.0])
def test_full_cell_raises_and_changes_nothing(capacity):
    """CellFullException(coordinate), and the agent stays where it was."""
    errors = []
    for move in MOVERS.values():
        _, grid, agents = world(capacity)
        a, b = grid._cells[(0, 0)], grid._cells[(0, 1)]
        move(agents[0], a)
        move(agents[1], b)
        before = snapshot(grid, agents)
        with pytest.raises(CellFullException) as info:
            move(agents[0], b)
        assert snapshot(grid, agents) == before
        errors.append((info.value.args, str(info.value), info.value.coordinate))
    assert errors[0] == errors[1]


def test_missing_agent_raises_from_the_value_error():
    """AgentMissingException chained from list.remove's ValueError, as in Python."""
    errors = []
    for move in MOVERS.values():
        _, grid, agents = world()
        agents[0]._modelly_cell = grid._cells[(1, 1)]  # claims a cell it is not in
        with pytest.raises(AgentMissingException) as info:
            move(agents[0], grid._cells[(2, 2)])
        exc = info.value
        assert isinstance(exc.__cause__, ValueError)
        assert exc.__context__ is exc.__cause__ and exc.__suppress_context__
        errors.append((str(exc), exc.__cause__.args, snapshot(grid, agents)))
    assert errors[0] == errors[1]


class Recording(Cell):
    """A Cell subclass whose overrides must still run."""

    __slots__ = ("log",)

    def __init__(self, coordinate):
        """A plain cell with a call log."""
        super().__init__(coordinate)
        self.log = []

    def add_agent(self, agent):
        """Record, then add."""
        self.log.append("add")
        super().add_agent(agent)

    def remove_agent(self, agent):
        """Record, then remove."""
        self.log.append("remove")
        super().remove_agent(agent)


class WithDict(Cell):
    """A subclass with an instance dict: an instance attribute may shadow a method."""


@pytest.mark.parametrize("name", list(MOVERS))
def test_overrides_and_instance_attributes_are_called(name):
    """Overrides run; a same-cell assignment calls nothing."""
    move = MOVERS[name]
    model = Model(rng=1)
    a, b = Recording((0,)), Recording((1,))
    agent = CellAgent(model)
    move(agent, a)
    move(agent, a)
    move(agent, b)
    assert (a.log, b.log) == (["add", "remove"], ["add"])
    shadowed, calls = WithDict((2,)), []
    shadowed.add_agent = calls.append
    move(agent, shadowed)
    assert calls == [agent] and not shadowed._agents and b.log[-1] == "remove"


@pytest.mark.parametrize("name", list(MOVERS))
def test_patching_cell_after_use_is_seen(name):
    """Changing Cell.add_agent after moves is picked up on the next move."""
    move = MOVERS[name]
    model = Model(rng=1)
    a, b = Cell((0,)), Cell((1,))
    agent = CellAgent(model)
    move(agent, a)
    original, seen = Cell.add_agent, []
    Cell.add_agent = lambda cell, ag: seen.append(cell) or original(cell, ag)
    try:
        move(agent, b)
    finally:
        Cell.add_agent = original
    assert seen == [b] and b._agents == [agent]


def test_errors_from_the_empty_setter_propagate():
    """An exception raised while writing ``empty`` reaches the caller."""

    class Brittle(Cell):
        __slots__ = ()

        @property
        def empty(self):
            return self._empty

        @empty.setter
        def empty(self, value):
            raise RuntimeError(value)

    model = Model(rng=1)
    for move in MOVERS.values():
        with pytest.raises(RuntimeError, match="False"):
            move(CellAgent(model), Brittle((0,)))


def test_no_reference_leaks():
    """Repeated moves and failures leave reference counts unchanged."""
    _, grid, agents = world(capacity=1)
    a, b = grid._cells[(0, 0)], grid._cells[(0, 1)]
    fastcell.set_cell(agents[1], b)
    tracked = [agents[0], agents[1], a, b, a.coordinate]
    before = [sys.getrefcount(x) for x in tracked]
    for _ in range(100):
        fastcell.set_cell(agents[0], a)
        with pytest.raises(CellFullException):
            fastcell.set_cell(agents[0], b)
        fastcell.set_cell(agents[0], None)
    assert [sys.getrefcount(x) for x in tracked] == before


def test_rejects_wrong_argument_counts():
    """Both entry points check their arity."""
    with pytest.raises(TypeError):
        fastcell.set_cell(object())
    with pytest.raises(TypeError):
        fastcell.bind(1, 2, 3)
