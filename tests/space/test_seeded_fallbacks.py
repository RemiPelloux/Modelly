"""Collections built without ``random`` take the model's generator when one is reachable."""

import warnings

import pytest

from modelly import Agent, Model
from modelly.core.agentset import AgentSet
from modelly.space import Cell, CellAgent, CellCollection, OrthogonalMooreGrid

SIZE = 10
DRAWS = 20
SEED = 42


def draws(collection: CellCollection) -> list:
    """Coordinates of repeated random cell picks: what a seed must reproduce."""
    return [collection.select_random_cell().coordinate for _ in range(DRAWS)]


def grid_draws(seed: int) -> list:
    """Random picks from a collection of a seeded grid's cells, built with no ``random``."""
    model = Model(rng=seed)
    grid = OrthogonalMooreGrid((SIZE, SIZE), random=model.random)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        collection = CellCollection(list(grid.all_cells))
    assert collection.random is model.random
    return draws(collection)


def agent_cell_draws(seed: int) -> list:
    """Random picks from cells with no generator of their own but holding an agent."""
    model = Model(rng=seed)
    cells = [Cell((i,)) for i in range(SIZE)]
    CellAgent(model).cell = cells[0]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        collection = CellCollection(cells)
    assert collection.random is model.random
    return draws(collection)


@pytest.mark.parametrize("build", [grid_draws, agent_cell_draws])
def test_same_seed_same_cells(build):
    """Same seed, same picks; another seed, other picks."""
    assert build(SEED) == build(SEED)
    assert build(SEED) != build(SEED + 1)


def test_no_generator_anywhere_still_warns():
    """Cells with no generator and no agent leave nothing to seed from."""
    with pytest.warns(UserWarning, match="Random number generator not specified"):
        CellCollection([Cell((i,)) for i in range(SIZE)])


def shuffled(seed: int) -> list[int]:
    """The order of a shuffled AgentSet built from agents with no ``random``."""
    model = Model(rng=seed)
    agents = [Agent(model) for _ in range(SIZE)]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        agentset = AgentSet(agents)
    assert agentset.random is model.random
    return [agent.unique_id for agent in agentset.shuffle()]


def test_agentset_takes_the_model_generator():
    """An AgentSet of a model's agents shuffles the same way for the same seed."""
    assert shuffled(SEED) == shuffled(SEED)
    assert shuffled(SEED) != shuffled(SEED + 1)
