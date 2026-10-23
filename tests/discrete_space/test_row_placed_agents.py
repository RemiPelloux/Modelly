"""Agents that keep their cell as a row column: listing, placement and drawing."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from modelly import Agent, Column, Model
from modelly.discrete_space import CellAgent, CellIndex, OrthogonalMooreGrid
from modelly.visualization.backends.matplotlib_backend import MatplotlibBackend
from modelly.visualization.components import AgentPortrayalStyle


class Walker(Agent):
    """An agent placed by its row column, in no cell's list."""

    row = Column(np.intp, default=0)

    def __init__(self, model, row):
        """Place the walker at ``row``."""
        super().__init__(model)
        self.row = row


class Sitter(CellAgent):
    """A classic agent held in its cell's list."""


def build():
    """A 4x3 grid with two row-placed walkers and one cell-list sitter."""
    model = Model(rng=1)
    grid = OrthogonalMooreGrid((4, 3), random=model.random)
    index = CellIndex(grid)
    Walker.create_agents(model, 2, row=[5, 11])
    sitter = Sitter(model)
    sitter.cell = grid[(0, 0)]
    return model, grid, index, sitter


def test_untracked_row_agents_are_not_in_the_space():
    """Before track(), the space lists only the cell-list agents."""
    _, grid, _, sitter = build()
    assert list(grid.agents) == [sitter]


def test_tracked_agents_are_listed_and_placed_at_their_row():
    """After track(), the space lists them and cell_of maps each row to its cell."""
    model, grid, index, sitter = build()
    index.track(model, Walker)
    listed = list(grid.agents)
    walkers = model.columns[Walker].agents
    assert listed == [sitter, *walkers]
    assert [index.cell_of(w).coordinate for w in walkers] == [(1, 2), (3, 2)]
    walkers[0].row = 0
    assert index.cell_of(walkers[0]) is grid[(0, 0)]


def test_matplotlib_backend_draws_row_placed_agents():
    """collect_agent_data places every agent, row-placed ones at their cell coordinate."""
    model, grid, index, _ = build()
    index.track(model, Walker)
    backend = MatplotlibBackend(space_drawer=MagicMock())
    data = backend.collect_agent_data(grid, lambda agent: AgentPortrayalStyle(size=5))
    assert sorted(map(tuple, data["loc"].tolist())) == [(0, 0), (1, 2), (3, 2)]


def test_cell_of_rejects_untracked_classes():
    """An untracked class has no cell to report."""
    model, _, index, _ = build()
    with pytest.raises(ValueError, match="not tracked"):
        index.cell_of(model.columns[Walker].agents[0])
