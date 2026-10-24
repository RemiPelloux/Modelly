"""Checkpoints of models with spaces: links, layers, indexes and positions survive."""

import networkx as nx
import numpy as np

from modelly import Model
from modelly.space import (
    CellAgent,
    CellIndex,
    Network,
    OrthogonalMooreGrid,
)
from modelly.space.continuous import ContinuousSpace, ContinuousSpaceAgent


def roundtrip(model, tmp_path):
    """Save ``model`` and load it back."""
    model.save(tmp_path / "space.ckpt")
    return Model.load(tmp_path / "space.ckpt")


def test_grid_agent_cell_links_and_layers_survive(tmp_path):
    """Agents and cells point at each other, and layers stay live, after a load."""
    model = Model(rng=1)
    model.grid = OrthogonalMooreGrid((5, 5), torus=True, random=model.random)
    model.grid.create_property_layer("sugar", default_value=2.0)
    for cell in model.random.sample(model.grid.all_cells.cells, 6):
        CellAgent(model).cell = cell
    model.grid[(1, 1)].sugar = 7.0
    _ = model.grid[(0, 0)].neighborhood  # fill a neighbourhood cache

    restored = roundtrip(model, tmp_path)
    grid = restored.grid
    for agent in restored.agents:
        assert agent in agent.cell.agents
        assert grid[agent.cell.coordinate] is agent.cell
    assert grid[(1, 1)].sugar == 7.0
    grid[(2, 2)].sugar = 3.0
    assert grid.sugar[2, 2] == 3.0 and grid.property_layers["sugar"] is grid.sugar
    corner = grid[(0, 0)]
    assert all(grid[n.coordinate] is n for n in corner.neighborhood)
    assert len(corner.neighborhood) == len(model.grid[(0, 0)].neighborhood)


def test_empty_cell_draws_continue_after_load(tmp_path):
    """The empties index is restored, so empty-cell draws match the original."""
    model = Model(rng=2)
    model.grid = OrthogonalMooreGrid((4, 4), random=model.random, capacity=1)
    model.grid._try_random = False
    for _ in range(9):
        CellAgent(model).cell = model.grid.select_random_empty_cell()
    restored = roundtrip(model, tmp_path)
    picks = [model.grid.select_random_empty_cell().coordinate for _ in range(5)]
    again = [restored.grid.select_random_empty_cell().coordinate for _ in range(5)]
    assert again == picks


def test_cell_index_and_network_survive(tmp_path):
    """A CellIndex over a network still maps rows to the restored cells."""
    model = Model(rng=3)
    model.network = Network(nx.cycle_graph(6), random=model.random)
    model.index = CellIndex(model.network)
    restored = roundtrip(model, tmp_path)
    cells = list(restored.network.all_cells)
    assert [cell.index for cell in cells] == list(range(6))
    assert restored.index.neighbor_sum(np.ones(6)).tolist() == [2.0] * 6


class Mover(ContinuousSpaceAgent):
    """A continuous-space agent."""

    def __init__(self, model, space, position):
        """Place the agent."""
        super().__init__(space, model)
        self.position = position


def test_continuous_positions_stay_a_view_after_load(tmp_path):
    """Moving an agent after a load updates the space's position array."""
    model = Model(rng=4)
    model.space = ContinuousSpace([[0, 10], [0, 10]], torus=True, random=model.random)
    for i in range(5):
        Mover(model, model.space, (i, i))
    model.space.neighbors_within(2.0)  # fill the neighbour cache
    restored = roundtrip(model, tmp_path)
    space = restored.space
    agent = space.active_agents[2]
    agent.position += np.array([0.5, 0.25])
    assert space._agent_positions[agent._modelly_index].tolist() == [2.5, 2.25]
    assert np.shares_memory(space.agent_positions, space._agent_positions)
    assert space._neighbors_cache is None
    Mover(restored, space, (9, 9))
    assert len(space.agent_positions) == len(space.active_agents) == 6
