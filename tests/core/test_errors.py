"""Errors that a model's own code triggers name the agent and the model time, not internals."""

import pytest

from modelly import Agent, Column, Model
from modelly._native import cells
from modelly.core.exceptions import (
    AgentMissingException,
    AgentRemovedError,
    CellFullException,
    ColumnMissingError,
)
from modelly.space import CellAgent, FixedAgent, OrthogonalMooreGrid
from modelly.space.continuous import ContinuousSpace, ContinuousSpaceAgent

INTERNALS = ("NoneType", "_column_table", "_remove_agent", "remove_agent", "_modelly")


class Sheep(CellAgent):
    """A grid agent with a column."""

    energy = Column(float, default=1.0)


class Patch(FixedAgent):
    """A fixed agent."""


class Forgetful(Agent):
    """An agent whose __init__ skips super().__init__."""

    size = Column(int)

    def __init__(self, model):  # noqa: D107
        self.size = 3


def world():
    """A model at time 2.0 with a 3x3 grid of capacity 1 and two sheep."""
    model = Model(rng=1)
    model.time = 2.0
    grid = OrthogonalMooreGrid((3, 3), capacity=1, random=model.random)
    first, second = Sheep(model), Sheep(model)
    first.cell, second.cell = grid._cells[(0, 0)], grid._cells[(0, 1)]
    return model, grid, first, second


def clean(message: str) -> bool:
    """Whether ``message`` mentions none of the framework's internals."""
    return not any(word in message for word in INTERNALS)


@pytest.mark.parametrize("move", [lambda a, c: setattr(a, "cell", c), Sheep.move_to])
def test_full_cell_names_the_agent_and_time(move):
    """Moving into a full cell raises CellFullException naming the agent and the time."""
    _, grid, _, second = world()
    with pytest.raises(CellFullException) as info:
        move(second, grid._cells[(0, 0)])
    message = str(info.value)
    assert f"Sheep {second.unique_id}" in message and "at time 2.0" in message
    assert "(0, 0)" in message and "full" in message and clean(message)
    assert info.value.agent is second and info.value.coordinate == (0, 0)


def test_full_cell_message_is_the_same_compiled_and_pure():
    """The C setter and its Python twin raise the same message."""
    messages = []
    for setter in (cells.py_set_cell, cells.set_cell):
        _, grid, _, second = world()
        with pytest.raises(CellFullException) as info:
            setter(second, grid._cells[(0, 0)])
        messages.append(str(info.value))
    assert messages[0] == messages[1]


def test_missing_agent_names_the_agent():
    """An agent that claims a cell it is not in is named, with the time."""
    _, grid, first, _ = world()
    first._modelly_cell = grid._cells[(2, 2)]
    with pytest.raises(AgentMissingException) as info:
        first.cell = grid._cells[(1, 1)]
    assert f"Sheep {first.unique_id} is not in the cell at (2, 2) at time 2.0" in str(
        info.value
    )


def test_fixed_agent_removed_twice():
    """A second remove() of a fixed agent names it; still an AttributeError."""
    model, grid, _, _ = world()
    patch = Patch(model)
    patch.cell = grid._cells[(2, 2)]
    patch.remove()
    with pytest.raises(AttributeError) as info:
        patch.remove()
    assert isinstance(info.value, AgentRemovedError)
    message = str(info.value)
    assert f"Patch {patch.unique_id}" in message and "at time 2.0" in message
    assert clean(message)


def test_continuous_agent_removed_twice():
    """A second remove() of a continuous-space agent names it."""
    model = Model(rng=1)
    space = ContinuousSpace([[0, 1], [0, 1]], random=model.random)
    agent = ContinuousSpaceAgent(space, model)
    agent.position = (0.5, 0.5)
    agent.remove()
    with pytest.raises(AgentRemovedError) as info:
        agent.remove()
    assert f"ContinuousSpaceAgent {agent.unique_id} at time 0.0" in str(info.value)
    assert "already removed" in str(info.value) and clean(str(info.value))


def test_column_of_a_removed_agent():
    """Reading or writing a Column of a removed agent names it instead of a stale row."""
    _, _, first, second = world()
    first.remove()
    for access in (lambda: first.energy, lambda: setattr(first, "energy", 2.0)):
        with pytest.raises(AttributeError) as info:
            access()
        assert isinstance(info.value, ColumnMissingError)
        message = str(info.value)
        assert f"Sheep {first.unique_id} has no 'energy' value at time 2.0" in message
        assert "removed" in message and clean(message)
    assert second.energy == 1.0  # the other agents' rows are untouched


def test_column_of_an_agent_never_added():
    """An __init__ without super().__init__ gets a message that says what to do."""
    with pytest.raises(ColumnMissingError) as info:
        Forgetful(Model(rng=1))
    message = str(info.value)
    assert "Forgetful None has no 'size' value" in message
    assert "super().__init__(model)" in message and clean(message)


def test_full_cell_without_an_agent_keeps_the_old_message():
    """Third-party code raising CellFullException(coordinate) still works."""
    assert str(CellFullException((1, 2))) == "Cell at coordinate (1, 2) is full."
