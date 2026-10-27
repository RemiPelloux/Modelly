"""Models that break the contract of modelly.distributed are refused with a reason."""

import networkx as nx
import numpy as np
import pytest

from modelly import Model
from modelly.core.columns import Column
from modelly.distributed import (
    Cluster,
    Max,
    Min,
    Partitionable,
    PartitionError,
    Phase,
    Sum,
    check_independence,
    partition,
)
from modelly.space import Network, OrthogonalMooreGrid
from modelly.space.cells.agents import CellAgent

SIDE = 8
PEOPLE = 40
SPLIT = partition.grid_blocks(2, 2)


class Walker(CellAgent):
    """A walker that counts the walkers around it."""

    def __init__(self, model, cell):
        """A walker in ``cell``."""
        super().__init__(model)
        self.cell = cell
        self.seen = 0

    def walk(self):
        """Step to a random neighbour cell from the walker's own stream."""
        self.cell = self.random.choice(self.cell.neighborhood.cells)

    def look(self):
        """Count the walkers in the cells around."""
        self.seen = sum(len(c.agents) for c in self.cell.neighborhood.cells)


def walkers(model):
    """Walkers in the partition (a reporter)."""
    return len(model.agents)


class Walk(Model):
    """A grid of walkers that declares a correct contract."""

    agent_streams = True
    capacity = None
    partitionable = Partitionable(
        space="grid",
        phases=(Phase("walk", moves=True), Phase("look", radius=1)),
        reporters={"walkers": Sum(walkers)},
    )

    def __init__(self, scenario=None):
        """Place the walkers at random cells."""
        super().__init__(scenario=scenario)
        self.grid = OrthogonalMooreGrid(
            (SIDE, SIDE), torus=True, capacity=self.capacity, random=self.random
        )
        cells = list(self.grid.all_cells)
        for pick in self.rng.integers(0, len(cells), PEOPLE).tolist():
            self.make(cells[pick])

    def make(self, cell):
        """Create one walker (a hook for the broken variants)."""
        return Walker(self, cell)

    def step(self):
        """The declared phases."""
        self.partitionable.step(self)


def _build(model_class, split=SPLIT):
    """Build ``model_class`` split by ``split`` on the local backend."""
    cluster = Cluster("local")
    return cluster.build(model_class, _scenario(), split)


def _scenario():
    """A fresh scenario."""
    from modelly.scenarios import Scenario  # noqa: PLC0415

    return Scenario(rng=3)


def test_a_correct_model_runs_split():
    """The reference variant builds, steps and keeps every walker."""
    model = _build(Walk)
    model.run_for(3)
    assert sum(model.population()) == PEOPLE
    assert model.collect()["walkers"].tolist() == [PEOPLE] * 4


def test_a_model_without_a_plan_is_refused():
    """No ``partitionable`` attribute: refused before any worker starts."""

    class Plain(Model):
        agent_streams = True

    with pytest.raises(PartitionError, match="declares no"):
        _build(Plain)


def test_a_model_without_agent_streams_is_refused():
    """Shared model generators cannot be split."""

    class Shared(Walk):
        agent_streams = False

    with pytest.raises(PartitionError, match="agent_streams"):
        _build(Shared)


def test_column_agents_are_refused():
    """Column-backed state does not travel between partitions yet."""

    class Counted(Walker):
        count = Column(np.int64)

    class WithColumns(Walk):
        def make(self, cell):
            return Counted(self, cell)

    with pytest.raises(PartitionError, match="Column"):
        _build(WithColumns)


def test_own_events_are_refused():
    """A model scheduling events of its own is refused."""

    class Scheduled(Walk):
        def __init__(self, scenario=None):
            super().__init__(scenario)
            self.schedule_event(self.step, at=5)

    with pytest.raises(PartitionError, match="events"):
        _build(Scheduled)


def test_moves_into_cells_with_a_capacity_are_refused():
    """Who gets a free cell would depend on the order agents move in."""

    class Crowded(Walk):
        capacity = PEOPLE

    with pytest.raises(PartitionError, match="capacity"):
        _build(Crowded)


def test_a_phase_naming_a_missing_method_is_refused():
    """The agents must have the phase's method."""

    class Flying(Walk):
        partitionable = Partitionable(space="grid", phases=(Phase("fly"),))

    with pytest.raises(PartitionError, match="no method"):
        _build(Flying)


def test_a_missing_space_is_refused():
    """The plan must name an attribute of the model."""

    class Elsewhere(Walk):
        partitionable = Partitionable(space="land", phases=(Phase("look"),))

    with pytest.raises(PartitionError, match="no attribute 'land'"):
        _build(Elsewhere)


def test_agents_outside_the_space_are_refused():
    """Every agent needs a place, so a partition owns it."""

    class Floating(Walk):
        def __init__(self, scenario=None):
            super().__init__(scenario)
            Walker(self, None)

    with pytest.raises(PartitionError, match="not in the partitioned space"):
        _build(Floating)


def test_a_partitioner_that_does_not_fit_the_space_is_refused():
    """Grid blocks cannot cut a network, k-d boxes cannot cut a grid."""

    class Networked(Walk):
        partitionable = Partitionable(space="network", phases=(Phase("look"),))

        def __init__(self, scenario=None):
            Model.__init__(self, scenario=scenario)
            self.network = Network(nx.path_graph(8), random=self.random)
            for cell in self.network.all_cells:
                Walker(self, cell)

    with pytest.raises(PartitionError, match="cannot split a Network"):
        _build(Networked)
    with pytest.raises(PartitionError, match="cannot split a OrthogonalMooreGrid"):
        _build(Walk, partition.kd(2))


class Shuffled(Walker):
    """Draws from the model's generator (a partition-dependent stream)."""

    def look(self):
        """Draw from model.random."""
        self.seen = self.model.random.random()


class Parent(Walker):
    """Walker 1 has a child keyed on its unique_id."""

    def look(self):
        """Create a walker."""
        if self.unique_id == 1:
            Walker(self.model, self.cell)


class Clinging(Walker):
    """Keeps a reference to an agent in its attributes."""

    def walk(self):
        """Remember itself, then walk."""
        self.friend = self
        super().walk()


def test_a_phase_drawing_from_the_model_generator_is_refused():
    """A draw from model.random depends on the partition: refused at that phase."""

    class UsesModelRandom(Walk):
        def make(self, cell):
            return Shuffled(self, cell)

    model = _build(UsesModelRandom)
    with pytest.raises(PartitionError, match="phase 'look' drew"):
        model.step()


def test_a_draw_from_the_grid_generator_is_refused():
    """The grid holds the model's generator: select_random_cell is refused too."""

    class GridWalker(Walker):
        def walk(self):
            self.cell = self.cell.neighborhood.select_random_cell()

    class UsesGridRandom(Walk):
        def make(self, cell):
            return GridWalker(self, cell)

    with pytest.raises(PartitionError, match="phase 'walk' drew"):
        _build(UsesGridRandom).step()


def test_births_keyed_on_unique_id_are_refused():
    """An agent created in a split run would get a partition-dependent stream key."""

    class Births(Walk):
        def make(self, cell):
            return Parent(self, cell)

    with pytest.raises(PartitionError, match="override stream_key"):
        _build(Births).run_for(1)


def test_attributes_referring_to_agents_are_refused():
    """A ghost cannot carry a reference to another agent."""

    class References(Walk):
        def make(self, cell):
            return Clinging(self, cell)

    with pytest.raises(PartitionError, match="refers to a Clinging"):
        _build(References).step()


def test_reading_past_the_declared_radius_is_caught_by_the_check():
    """A phase that looks one cell away but declares radius 0 differs when split."""

    class Shortsighted(Walk):
        partitionable = Partitionable(
            space="grid",
            phases=(Phase("walk", moves=True), Phase("look")),
            reporters={"seen": Sum(lambda model: sum(a.seen for a in model.agents))},
        )

    with pytest.raises(PartitionError, match="differs from one process"):
        check_independence(Shortsighted, _scenario(), [SPLIT], 3)


def test_reducers_combine_parts():
    """Sum is exact on integers and fsum on floats; Min and Max pick parts."""
    assert Sum(len).combine([1, 2, np.int64(3)]) == 6
    assert Sum(len).combine([0.1] * 10) == 1.0
    assert Min(len).combine([3, 1, 2]) == 1
    assert Max(len).combine([3, np.int64(5), 2]) == 5


def test_declarations_are_validated():
    """A negative radius and an empty phase list are refused."""
    with pytest.raises(ValueError, match="radius"):
        Phase("look", radius=-1)
    with pytest.raises(ValueError, match="at least one phase"):
        Partitionable(space="grid", phases=())
