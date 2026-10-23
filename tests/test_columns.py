"""Tests for columnar agent state (modelly.columns)."""

import copy
import pickle

import numpy as np
import pytest

from modelly import Agent, Column, Model
from modelly.agentset import AgentSet
from modelly.columns import INITIAL_CAPACITY, ColumnTable


class Wealthy(Agent):
    """An agent with two columns."""

    wealth = Column(int, default=1)
    score = Column(float, default=0.5)

    def __init__(self, model, wealth=None):
        """Create the agent, optionally overriding the wealth default."""
        super().__init__(model)
        if wealth is not None:
            self.wealth = wealth


class Richer(Wealthy):
    """A subclass inheriting the columns and adding one."""

    bonus = Column(int, default=3)


class Plain(Agent):
    """An agent without columns."""


def test_column_specs_collected_in_mro_order():
    """Column specs collected in mro order."""
    assert list(Wealthy._column_specs) == ["wealth", "score"]
    assert list(Richer._column_specs) == ["wealth", "score", "bonus"]
    assert Plain._column_specs == {}
    assert Wealthy.wealth is Wealthy._column_specs["wealth"]


def test_agent_reads_and_writes_its_row():
    """Agent reads and writes its row."""
    model = Model(rng=1)
    a, b = Wealthy(model), Wealthy(model, wealth=7)
    assert a.wealth == 1 and b.wealth == 7
    assert a.score == pytest.approx(0.5)
    a.wealth += 4
    assert a.wealth == 5
    table = model.columns[Wealthy]
    assert table.wealth.tolist() == [5, 7]
    assert table.unique_id.tolist() == [a.unique_id, b.unique_id]
    assert table["score"].shape == (2,)


def test_table_view_is_live_and_bulk_updates_reach_agents():
    """Table view is live and bulk updates reach agents."""
    model = Model(rng=1)
    agents = [Wealthy(model, wealth=i) for i in range(5)]
    table = model.columns[Wealthy]
    table.wealth[table.wealth >= 3] -= 10
    assert [a.wealth for a in agents] == [0, 1, 2, -7, -6]
    assert len(table) == 5
    assert "wealth" in table and "nope" not in table


def test_where_returns_weak_agentset_in_row_order():
    """Where returns weak agentset in row order."""
    model = Model(rng=1)
    agents = [Wealthy(model, wealth=i) for i in range(6)]
    table = model.columns[Wealthy]
    rich = table.where(table.wealth > 2)
    assert isinstance(rich, AgentSet)
    assert rich.to_list() == agents[3:]
    assert table.where(table.wealth > 100).to_list() == []


def test_plain_agents_have_no_table():
    """Plain agents have no table."""
    model = Model(rng=1)
    Plain(model)
    assert Plain not in model.columns
    assert len(model.columns) == 0
    with pytest.raises(KeyError, match="no column table"):
        model.columns[Plain]


def test_subclass_gets_its_own_table():
    """Subclass gets its own table."""
    model = Model(rng=1)
    Wealthy(model)
    r = Richer(model)
    assert set(model.columns) == {Wealthy, Richer}
    assert r.bonus == 3
    assert model.columns[Richer].columns == ["unique_id", "wealth", "score", "bonus"]
    assert len(model.columns[Wealthy]) == 1


def test_remove_moves_last_row_into_the_freed_slot():
    """Remove moves last row into the freed slot."""
    model = Model(rng=1)
    agents = [Wealthy(model, wealth=i) for i in range(4)]
    table = model.columns[Wealthy]
    agents[1].remove()
    assert len(table) == 3
    assert table.agents == [agents[0], agents[3], agents[2]]
    assert table.wealth.tolist() == [0, 3, 2]
    assert agents[3].wealth == 3 and agents[3]._column_row == 1
    assert agents[1]._column_row == -1
    # removing the last row needs no move
    agents[2].remove()
    assert table.agents == [agents[0], agents[3]]
    # a removed agent can be removed again without touching the table
    agents[1].remove()
    assert len(table) == 2


def test_table_grows_past_initial_capacity():
    """Table grows past initial capacity."""
    model = Model(rng=1)
    n = INITIAL_CAPACITY * 2 + 5
    agents = [Wealthy(model, wealth=i) for i in range(n)]
    table = model.columns[Wealthy]
    assert len(table) == n
    assert table.wealth.tolist() == list(range(n))
    assert table.score.tolist() == [0.5] * n
    assert agents[-1].wealth == n - 1


def test_to_dataframe_is_a_copy_indexed_by_unique_id():
    """To dataframe is a copy indexed by unique id."""
    model = Model(rng=1)
    agents = [Wealthy(model, wealth=i) for i in range(3)]
    frame = model.columns[Wealthy].to_dataframe()
    assert list(frame.columns) == ["wealth", "score"]
    assert frame.index.tolist() == [a.unique_id for a in agents]
    frame["wealth"] += 100
    assert agents[0].wealth == 0


def test_model_with_columns_pickles_and_deepcopies():
    """Model with columns pickles and deepcopies."""
    model = Model(rng=1)
    agents = [Wealthy(model, wealth=i) for i in range(3)]
    agents[0].remove()
    for clone in (pickle.loads(pickle.dumps(model)), copy.deepcopy(model)):  # noqa: S301
        table = clone.columns[Wealthy]
        assert table.wealth.tolist() == [2, 1]
        for agent in table.agents:
            assert agent.wealth == table.wealth[agent._column_row]
            assert agent._column_table is table


def test_remove_all_agents_empties_the_table():
    """Remove all agents empties the table."""
    model = Model(rng=1)
    for i in range(5):
        Wealthy(model, wealth=i)
    model.remove_all_agents()
    assert len(model.columns[Wealthy]) == 0
    assert isinstance(model.columns[Wealthy], ColumnTable)
    Wealthy(model, wealth=9)
    assert model.columns[Wealthy].wealth.tolist() == [9]


def test_repr_hides_column_bookkeeping():
    """Repr hides column bookkeeping."""
    model = Model(rng=1)
    a = Wealthy(model)
    assert "_column" not in repr(a)
    assert repr(Wealthy.wealth) == "Column(int64, default=1)"
    assert np.dtype(int) == Wealthy.wealth.dtype


def test_remove_where_removes_masked_agents():
    """Remove where removes exactly the masked agents and keeps the table consistent."""
    model = Model(rng=1)
    agents = [Wealthy(model, wealth=i) for i in range(6)]
    table = model.columns[Wealthy]
    removed = table.remove_where(table.wealth % 2 == 0)
    assert removed == 3
    assert sorted(table.wealth.tolist()) == [1, 3, 5]
    assert len(model.agents) == 3
    assert all(agent._column_row == -1 for agent in agents[::2])
    for agent in table.agents:
        assert table.wealth[agent._column_row] == agent.wealth
    assert table.remove_where(np.zeros(3, dtype=bool)) == 0


class Spawner(Agent):
    """An agent that can reproduce, for the do_where test."""

    energy = Column(float, default=1.0)

    def spawn(self):
        """Create one offspring."""
        Spawner(self.model)


def test_draw_is_seeded_and_per_row():
    """draw() gives one Bernoulli draw per row from the model's numpy generator."""
    a, b = Model(rng=7), Model(rng=7)
    for model in (a, b):
        for _ in range(50):
            Spawner(model)
    mask_a = a.columns[Spawner].draw(0.3)
    mask_b = b.columns[Spawner].draw(0.3)
    assert mask_a.shape == (50,) and mask_a.dtype == bool
    assert mask_a.tolist() == mask_b.tolist()
    assert not a.columns[Spawner].draw(0.0).any()
    assert a.columns[Spawner].draw(1.0).all()
    per_row = np.where(np.arange(50) < 10, 1.0, 0.0)
    assert a.columns[Spawner].draw(per_row).sum() == 10


def test_do_where_calls_the_masked_agents_and_tolerates_growth():
    """do_where snapshots the agents, so spawning during the call is safe."""
    model = Model(rng=1)
    for _ in range(6):
        Spawner(model)
    table = model.columns[Spawner]
    mask = np.arange(6) % 2 == 0
    assert table.do_where(mask, "spawn") == 3
    assert len(table) == 9
    assert len(model.agents) == 9


class Cohort(Agent):
    """A super-individual: one row standing for ``count`` identical insects."""

    count = Column(int, default=0)


def test_thin_draws_binomial_survivors_in_place():
    """thin() replaces every count by Binomial(count, survival) and returns the view."""
    model = Model(rng=7)
    for _ in range(50):
        cohort = Cohort(model)
        cohort.count = 1000
    table = model.columns[Cohort]
    survivors = table.thin("count", 0.9)
    assert survivors is not None and survivors.shape == (50,)
    assert (survivors <= 1000).all() and (survivors >= 0).all()
    assert abs(survivors.mean() - 900) < 15
    assert table.count.tolist() == survivors.tolist()
    assert table.thin("count", 0.0).sum() == 0
    assert table.thin("count", 1.0).sum() == 0


def test_assigning_a_table_column_writes_the_rows_in_place():
    """table.col = values and table.col -= 1 update the column, never shadow it."""
    model = Model(rng=1)
    agents = [Wealthy(model) for _ in range(4)]
    table = model.columns[Wealthy]
    table.wealth -= 1
    assert [a.wealth for a in agents] == [0, 0, 0, 0]
    table.wealth = np.arange(4)
    assert agents[3].wealth == 3
    for _ in range(INITIAL_CAPACITY):
        Wealthy(model)
    table.wealth += 1
    assert agents[3].wealth == 4
