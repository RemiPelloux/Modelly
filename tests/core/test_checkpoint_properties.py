"""Property-based tests for checkpoints: a random small model survives a round trip."""

from hypothesis import given
from hypothesis import strategies as st

from modelly import Agent, Model
from modelly.core.checkpoint import checkpoint_bytes, model_from_bytes
from modelly.core.columns import Column
from modelly.dev.digest import run_digest
from modelly.space import CellAgent, OrthogonalMooreGrid

MAX_AGENTS = 15
MAX_STEPS = 6
GRID_SIDE = 5


class Saver(Agent):
    """Saves a random share of its wealth each step."""

    wealth = Column(float, default=1.0)

    def step(self):  # noqa: D102
        self.wealth += self.random.random() * self.model.rng.random()


class Walker(CellAgent):
    """Walks to a random neighbouring cell each step."""

    def step(self):  # noqa: D102
        self.cell = self.cell.neighborhood.select_random_cell()
        self.steps_taken = getattr(self, "steps_taken", 0) + 1


class Mixed(Model):
    """Savers and walkers on a torus."""

    def __init__(self, savers=1, walkers=1, rng=None):  # noqa: D107
        super().__init__(rng=rng)
        self.grid = OrthogonalMooreGrid(
            (GRID_SIDE, GRID_SIDE), torus=True, random=self.random
        )
        Saver.create_agents(self, savers)
        for _ in range(walkers):
            Walker(self).cell = self.grid.select_random_empty_cell()

    def step(self):  # noqa: D102
        self.agents.shuffle_do("step")


@given(
    seed=st.integers(0, 2**32 - 1),
    savers=st.integers(0, MAX_AGENTS),
    walkers=st.integers(0, MAX_AGENTS),
    before=st.integers(1, MAX_STEPS),
    after=st.integers(1, MAX_STEPS),
    compress=st.booleans(),
)
def test_round_trip_resumes_the_same_run(
    seed, savers, walkers, before, after, compress
):
    """Loading a checkpoint gives the same state now and the same run afterwards."""
    model = Mixed(savers, walkers, rng=seed)
    model.run_for(before)
    restored = model_from_bytes(checkpoint_bytes(model, compress=compress))
    assert run_digest(restored) == run_digest(model)
    model.run_for(after)
    restored.run_for(after)
    assert run_digest(restored) == run_digest(model)
    assert restored.time == model.time
