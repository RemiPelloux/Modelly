"""Tests for reporter normalisation and the fast agent-row collection paths."""

from functools import partial

import pytest

from modelly import Agent, Column, Model
from modelly.data.reporters import (
    _whole_column_table,
    collect_agent_rows,
    collect_model_value,
    make_agent_reporter,
    snapshot,
    validate_model_reporter,
)


class Rich(Agent):
    """Wealth and score kept as columns."""

    wealth = Column(int, default=1)
    score = Column(float, default=0.5)


class Other(Rich):
    """A second class sharing the columns."""


class Plain(Agent):
    """Ordinary attributes."""

    def __init__(self, model, wealth):
        """Create the instance."""
        super().__init__(model)
        self.wealth = wealth
        self.items = [wealth]


def _reporters(*names):
    return {name: make_agent_reporter(name, name) for name in names}


class _Holder:
    def __init__(self):
        self.value = 3
        self.items = [1, 2]

    def method(self):
        return self.items


def test_collect_model_value_every_reporter_kind():
    """Collect model value every reporter kind."""
    model = _Holder()
    assert collect_model_value("l", lambda m: m.value * 2, model) == 6
    assert collect_model_value("p", partial(lambda m, k: m.value + k, k=1), model) == 4
    assert collect_model_value("s", "value", model) == 3
    assert collect_model_value("missing", "nope", model) is None
    assert collect_model_value("list", [max, [[4, 9]]], model) == 9
    copied = collect_model_value("m", model.method, model)
    assert copied == [1, 2]
    assert copied is not model.items


def test_collect_model_value_rechecks_list_reporters():
    """Collect model value rechecks list reporters."""
    with pytest.raises(ValueError, match="format"):
        collect_model_value("bad", [max], _Holder())


def test_validate_model_reporter_list_format():
    """Validate model reporter list format."""
    validate_model_reporter("ok", [max, [1, 2]], _Holder())
    with pytest.raises(ValueError, match="second element must be a list"):
        validate_model_reporter("bad", [max, 3], _Holder())


def test_whole_column_table_rows_come_from_the_table():
    """Whole column table rows come from the table."""
    model = Model(rng=1)
    agents = [Rich(model) for _ in range(3)]
    for i, agent in enumerate(agents):
        agent.wealth = 10 * i
        agent.score = i / 2
    reporters = _reporters("wealth", "score")
    assert _whole_column_table(agents, ["wealth", "score"]) is not None
    rows = collect_agent_rows(agents, reporters, time=2)
    assert rows == [
        (2, agents[0].unique_id, 0, 0.0),
        (2, agents[1].unique_id, 10, 0.5),
        (2, agents[2].unique_id, 20, 1.0),
    ]
    assert all(type(row[2]) is int for row in rows)


def test_whole_column_table_rejects_partial_populations():
    """Whole column table rejects partial populations."""
    model = Model(rng=1)
    agents = [Rich(model) for _ in range(3)]
    assert _whole_column_table(agents[:2], ["wealth"]) is None
    assert _whole_column_table([], ["wealth"]) is None
    assert _whole_column_table(agents, ["wealth", None]) is None
    assert _whole_column_table(agents, ["unknown"]) is None
    assert _whole_column_table([Plain(model, 1)], ["wealth"]) is None
    rows = collect_agent_rows(agents[:2], _reporters("wealth"), time=0)
    assert [row[2] for row in rows] == [1, 1]


def test_whole_column_table_rejects_mixed_classes():
    """Whole column table rejects mixed classes."""
    model = Model(rng=1)
    agents = [Rich(model), Other(model)]
    assert _whole_column_table(agents, ["wealth"]) is None


def test_attribute_rows_copy_mutable_values():
    """Attribute rows copy mutable values."""
    model = Model(rng=1)
    agents = [Plain(model, 1), Plain(model, 2)]
    rows = collect_agent_rows(agents, _reporters("wealth", "items"), time=1)
    assert [row[2:] for row in rows] == [(1, [1]), (2, [2])]
    agents[0].items.append(99)
    assert rows[0][3] == [1]


def test_missing_attribute_falls_back_to_descriptive_error():
    """Missing attribute falls back to descriptive error."""
    model = Model(rng=1)
    agents = [Plain(model, 1)]
    with pytest.raises(AttributeError, match="has no attribute 'ghost'"):
        collect_agent_rows(agents, _reporters("wealth", "ghost"), time=0)


def test_list_and_callable_agent_reporters():
    """List and callable agent reporters."""
    model = Model(rng=1)
    agents = [Plain(model, 3)]
    reporters = {
        "scaled": make_agent_reporter("scaled", [lambda a, k: a.wealth * k, [5]]),
        "fn": make_agent_reporter("fn", lambda a: a.wealth + 1),
    }
    assert collect_agent_rows(agents, reporters, time=0)[0][2:] == (15, 4)


def test_snapshot_copies_only_mutable_values():
    """Snapshot copies only mutable values."""
    value = (1, "a")
    assert snapshot(value) is value
    data = {"k": [1]}
    copy = snapshot(data)
    assert copy == data
    assert copy is not data
