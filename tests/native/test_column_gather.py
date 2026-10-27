"""The compiled attribute gather reads Column attributes exactly as their getters do."""

import numpy as np
import pytest

from modelly import Agent, Column, Model
from modelly._native import sets
from modelly.core.exceptions import ColumnMissingError
from modelly.data.collector import DataCollector

pytestmark = pytest.mark.skipif(not sets.NATIVE, reason="fastset is not built")
fastset = sets._fastset


class Sheep(Agent):
    """Columns of several dtypes, some a memoryview cannot index."""

    energy = Column(float, default=1.5)
    age = Column(np.int8, default=3)
    alive = Column(bool, default=True)
    weight = Column(np.float32, default=0.25)
    tag = Column("U4", default="ab")
    note = Column(object, default=None)


class Wolf(Agent):
    """Another table, with the same column name at another position."""

    alive = Column(bool, default=False)
    energy = Column(float, default=9.0)


class Lamb(Sheep):
    """A subclass: its own table and its own properties."""


class Plain(Agent):
    """No columns: ``energy`` is an instance attribute."""

    def __init__(self, model):
        """Keep a plain value."""
        super().__init__(model)
        self.energy = -1.0
        self.alive = 1


class Masked(Sheep):
    """Its ``energy`` column is replaced by a plain property after the class is made."""


# In the class body the column would win: Agent reinstalls inherited columns.
Masked.energy = property(lambda self: "masked")


NAMES = ("energy", "age", "alive", "weight", "tag", "note", "unique_id")


def mixed_population():
    """A model whose agents interleave the classes, with rows moved by removals."""
    model = Model(rng=2)
    kinds = (Sheep, Wolf, Lamb, Plain, Sheep, Wolf)
    agents = [kinds[i % len(kinds)](model) for i in range(60)]
    for i, agent in enumerate(agents):
        if not isinstance(agent, Plain):
            agent.energy = i * 0.5
    for agent in agents[3:20:4]:
        agent.remove()
    return model, list(model.agents)


@pytest.mark.parametrize("name", ["energy", "alive", "unique_id"])
def test_mixed_classes_match_attrgetter(name):
    """Same values, same types, in the same order, across tables and plain agents."""
    _, agents = mixed_population()
    expected = sets.py_attr_values(agents, name)
    got = fastset.attr_values(agents, name)
    assert got == expected
    assert list(map(type, got)) == list(map(type, expected))


@pytest.mark.parametrize("name", NAMES)
def test_every_dtype_matches(name):
    """memoryview-backed and ndarray-backed columns alike."""
    model = Model(rng=1)
    agents = [cls(model) for cls in (Sheep, Lamb) * 5]
    expected = sets.py_attr_values(agents, name)
    got = fastset.attr_values(agents, name)
    assert [repr(v) for v in got] == [repr(v) for v in expected]


def test_an_overriding_property_is_called():
    """A subclass property that replaces the column is not read from the table."""
    model = Model(rng=1)
    agents = [Sheep(model), Masked(model), Sheep(model)]
    assert fastset.attr_values(agents, "energy") == [1.5, "masked", 1.5]


def test_a_removed_agent_raises_the_getter_error():
    """No row: the getter's ColumnMissingError, as attrgetter raises it."""
    model = Model(rng=1)
    agents = [Sheep(model), Sheep(model)]
    agents[1].remove()
    with pytest.raises(ColumnMissingError):
        sets.py_attr_values(agents, "energy")
    with pytest.raises(ColumnMissingError):
        fastset.attr_values(agents, "energy")


def test_a_table_grown_between_calls_is_reread():
    """The cached view is per call: a grown table's new arrays are read."""
    model = Model(rng=1)
    first = [Sheep(model) for _ in range(3)]
    assert fastset.attr_values(first, "energy") == [1.5] * 3
    for _ in range(200):  # grows the table past its initial capacity
        Sheep(model)
    first[0].energy = 7.0
    assert fastset.attr_values(first, "energy") == [7.0, 1.5, 1.5]


def test_a_class_changed_after_a_gather_is_looked_up_again():
    """Replacing the property on the class is seen through its version tag."""

    class Ewe(Agent):
        wool = Column(float, default=2.0)

    model = Model(rng=1)
    agents = [Ewe(model) for _ in range(3)]
    assert fastset.attr_values(agents, "wool") == [2.0] * 3
    Ewe.wool = property(lambda self: "replaced")
    assert fastset.attr_values(agents, "wool") == ["replaced"] * 3


def records(model, reporters):
    """What a DataCollector records for these agent reporters, compiled and pure."""
    compiled = DataCollector(agent_reporters=reporters)
    compiled.collect(model)
    native, sets.NATIVE = sets.NATIVE, False
    try:
        pure = DataCollector(agent_reporters=reporters)
        pure.collect(model)
    finally:
        sets.NATIVE = native
    return compiled._agent_records, pure._agent_records


@pytest.mark.parametrize(
    "reporters",
    [
        {"energy": "energy"},
        {"energy": "energy", "alive": "alive", "id": "unique_id"},
        {"energy": "energy", "double": lambda a: 2 * a.unique_id},
    ],
)
def test_collector_rows_are_identical(reporters):
    """Mixed classes, all-attribute and mixed reporters: the same rows."""
    model, _ = mixed_population()
    compiled, pure = records(model, reporters)
    assert compiled == pure
