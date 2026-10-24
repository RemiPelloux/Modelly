"""Property-based tests for cell spaces: an agent is in exactly the cell it says it is."""

from hypothesis import given
from hypothesis import strategies as st

from modelly import Model
from modelly.space import CellAgent, OrthogonalMooreGrid

MAX_SIDE = 6
MAX_AGENTS = 12
MAX_MOVES = 40


def _consistent(grid, agents):
    """Agent to cell and cell to agent agree, and every agent is counted once."""
    held = [a for cell in grid.all_cells for a in cell.agents]
    assert len(held) == len(set(held)) == len(agents)
    for agent in agents:
        assert agent in agent.cell.agents
    for cell in grid.all_cells:
        assert all(a.cell is cell for a in cell.agents)


@given(
    seed=st.integers(0, 2**32 - 1),
    side=st.integers(1, MAX_SIDE),
    n=st.integers(1, MAX_AGENTS),
    moves=st.lists(
        st.tuples(st.integers(0, MAX_AGENTS), st.integers(0, 2**16)), max_size=MAX_MOVES
    ),
    torus=st.booleans(),
)
def test_membership_survives_random_moves(seed, side, n, moves, torus):
    """After any moves (to a random cell or a neighbour) membership is consistent."""
    model = Model(rng=seed)
    grid = OrthogonalMooreGrid((side, side), torus=torus, random=model.random)
    cells = grid.all_cells.cells
    agents = [CellAgent(model) for _ in range(n)]
    for i, agent in enumerate(agents):
        agent.cell = cells[i % len(cells)]
    for who, where in moves:
        agent = agents[who % n]
        if where % 2:
            agent.move_to(cells[where % len(cells)])
        elif len(agent.cell.neighborhood):
            agent.cell = agent.cell.neighborhood.select_random_cell()
    _consistent(grid, agents)


@given(
    seed=st.integers(0, 2**32 - 1),
    n=st.integers(1, MAX_AGENTS),
    gone=st.integers(0, MAX_AGENTS),
)
def test_removed_agents_leave_their_cell(seed, n, gone):
    """Removing agents takes them out of their cells and nothing else."""
    model = Model(rng=seed)
    grid = OrthogonalMooreGrid((MAX_SIDE, MAX_SIDE), random=model.random)
    agents = [CellAgent(model) for _ in range(n)]
    for agent in agents:
        agent.cell = grid.select_random_empty_cell()
    for agent in agents[: gone % (n + 1)]:
        agent.remove()
    _consistent(grid, agents[gone % (n + 1) :])
