"""Property-based tests for column tables: rows stay in step with the agents."""

import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from modelly import Agent, Model
from modelly.core.columns import Column

MAX_AGENTS = 40
MAX_VALUE = 1000


class Holder(Agent):
    """An agent with one integer and one float column."""

    wealth = Column(int, default=1)
    energy = Column(float, default=0.5)


def _consistent(model):
    if Holder not in model.columns:  # no Holder was ever created
        assert not model.agents
        return None
    table = model.columns[Holder]
    agents = table.agents
    assert sorted(agents, key=lambda a: a.unique_id) == sorted(
        model.agents, key=lambda a: a.unique_id
    )
    assert table["unique_id"].tolist() == [a.unique_id for a in agents]
    assert table.wealth.tolist() == [a.wealth for a in agents]
    assert table.energy.tolist() == [a.energy for a in agents]
    return table


# A program: ("add", wealth) or ("remove", index into the live agents).
operations = st.lists(
    st.one_of(
        st.tuples(st.just("add"), st.integers(0, MAX_VALUE)),
        st.tuples(st.just("remove"), st.integers(0, MAX_AGENTS)),
    ),
    max_size=MAX_AGENTS,
)


@given(seed=st.integers(0, 2**32 - 1), program=operations)
def test_add_and_remove_keep_rows_and_agents_in_step(seed, program):
    """After any sequence of adds and removes, every row holds its own agent's values."""
    model = Model(rng=seed)
    for op, value in program:
        if op == "add":
            Holder(model).wealth = value
        elif len(model.agents):
            list(model.agents)[value % len(model.agents)].remove()
    table = _consistent(model)
    assert len(model.agents) == (0 if table is None else len(table))


@given(
    seed=st.integers(0, 2**32 - 1),
    wealths=st.lists(st.integers(0, MAX_VALUE), min_size=1, max_size=MAX_AGENTS),
    cut=st.integers(0, MAX_VALUE),
)
def test_where_and_remove_where_select_exactly_the_mask(seed, wealths, cut):
    """The masked agents are selected by where and removed by remove_where, no others."""
    model = Model(rng=seed)
    for wealth in wealths:
        Holder(model).wealth = wealth
    table = model.columns[Holder]
    chosen = {a.unique_id for a in table.where(table.wealth > cut)}
    assert chosen == {a.unique_id for a in model.agents if a.wealth > cut}
    removed = table.remove_where(table.wealth > cut)
    assert removed == len(chosen)
    assert not chosen & {a.unique_id for a in model.agents}
    assert all(a.wealth <= cut for a in model.agents)
    _consistent(model)


@given(
    seed=st.integers(0, 2**32 - 1),
    n=st.integers(1, MAX_AGENTS),
    p=st.floats(0.0, 1.0),
)
def test_draw_is_one_seeded_bernoulli_per_row(seed, n, p):
    """One seeded boolean per row: all False at p=0, all True at p=1."""
    draws = []
    for _ in range(2):
        model = Model(rng=seed)
        Holder.create_agents(model, n)
        draws.append(model.columns[Holder].draw(p))
    assert draws[0].dtype == np.bool_ and draws[0].shape == (n,)
    assert np.array_equal(draws[0], draws[1])
    if p == 0.0:
        assert not draws[0].any()
    if p == 1.0:
        assert draws[0].all()
