"""Tests for building only a partition's agents (modelly.distributed.building)."""

import pytest

from modelly import Model
from modelly.distributed import Cluster, Partitionable, PartitionError, Phase, partition
from modelly.distributed.building import building, owns
from modelly.examples.distributed.continuous_sir import ContinuousSIR, WalkerScenario
from modelly.examples.distributed.grid_epidemic import EpidemicScenario, GridEpidemic
from modelly.space import OrthogonalMooreGrid
from modelly.space.cells.agents import CellAgent

SIDE = 12
SPLIT = partition.grid_blocks(2, 2)


def test_owns_is_always_true_in_one_process():
    """Outside a split build every location belongs to the process."""
    model = GridEpidemic(EpidemicScenario(rng=1, width=SIDE, height=SIDE, people=50))
    assert owns(model, (0, 0))
    assert len(model.agents) == 50


def test_a_split_build_creates_only_the_blocks_people():
    """Each worker builds its block's people; together they are everyone."""
    scenario = EpidemicScenario(rng=1, width=SIDE, height=SIDE, people=200)
    with Cluster("local") as cluster:
        model = cluster.build(GridEpidemic, scenario, SPLIT)
        built = [entry[0] for entry in model.info()]
    assert sum(built) == scenario.people
    assert max(built) < scenario.people


def test_owns_answers_for_the_partition_being_built():
    """Inside ``building`` owns follows the layout of the model's space."""
    model = GridEpidemic(EpidemicScenario(rng=1, width=SIDE, height=SIDE, people=10))
    with building(SPLIT, 3) as build:
        assert owns(model, (SIDE - 1, SIDE - 1))
        assert not owns(model, (0, 0))
    assert build.layout is not None
    assert owns(model, (0, 0))


def test_kd_splits_cannot_answer_owns():
    """k-d boxes depend on the built positions: owns is refused."""
    model = ContinuousSIR(WalkerScenario(rng=1, people=10))
    with building(partition.kd(2), 0), pytest.raises(PartitionError, match="kd"):
        owns(model, (0.0, 0.0))


class Settler(CellAgent):
    """A walker keyed on its unique_id (the default stream key)."""

    def __init__(self, model, cell):
        """A settler in ``cell``."""
        super().__init__(model)
        self.cell = cell

    def rest(self):
        """Do nothing."""


class Partial(Model):
    """Builds only its own settlers but keeps the default stream keys."""

    agent_streams = True
    partitionable = Partitionable(space="grid", phases=(Phase("rest"),))

    def __init__(self, scenario=None):
        """One settler per owned cell."""
        super().__init__(scenario=scenario)
        self.grid = OrthogonalMooreGrid((SIDE, SIDE), random=self.random)
        for cell in self.grid.all_cells:
            if owns(self, cell.coordinate):
                Settler(self, cell)


def test_partial_builds_with_default_keys_are_refused():
    """Different builds would number the agents, and so key their streams, apart."""
    from modelly.scenarios import Scenario  # noqa: PLC0415

    with pytest.raises(PartitionError, match="override stream_key"):
        Cluster("local").build(Partial, Scenario(rng=1), SPLIT)
