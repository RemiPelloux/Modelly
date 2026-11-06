"""Columnar agent records: the rows readers see and the frames exported from them."""

import copy
import itertools
import pickle

import numpy as np
import pandas as pd
import pytest

from modelly import Agent, Model
from modelly.data import DataCollector
from modelly.data._records import AgentRows, FrameCache, growing_frame, records_frame


def from_rows(records, names):
    """The export as it was built before: DataFrame.from_records over the row tuples."""
    rows = list(itertools.chain.from_iterable(records))
    return pd.DataFrame.from_records(
        rows, columns=["Step", "AgentID", *names], index=["Step", "AgentID"]
    )


def assert_same(a, b):
    """Equal frames, dtypes included."""
    pd.testing.assert_frame_equal(a, b, check_exact=True, check_index_type=True)
    assert list(a.dtypes) == list(b.dtypes)


def test_agent_rows_read_as_the_old_tuples():
    """Iteration, indexing, equality, pickling and repr give the row tuples."""
    rows = AgentRows(3.0, [1, 2], [[5, 6], ["a", "b"]])
    assert list(rows) == [(3.0, 1, 5, "a"), (3.0, 2, 6, "b")]
    assert rows == list(rows) and rows[-1] == (3.0, 2, 6, "b")
    assert rows[:1] == [(3.0, 1, 5, "a")] and len(rows) == 2
    assert pickle.loads(pickle.dumps(rows)) == rows  # noqa: S301
    assert copy.deepcopy(rows) == rows
    assert repr(rows) == repr(list(rows))


COLUMNS = {
    "int": [1, 2, 3],
    "float": [1.5, -0.0, np.nan],
    "bool": [True, False, True],
    "numpy": [np.float64(1.5), 2.0, 3.0],
    "mixed": [1, 2.5, None],
    "str": ["a", None, "c"],
    "tuple": [(1, 2), (3, 4), (5, 6)],
    "big": [2**63, 1, 2],
}


@pytest.mark.parametrize(("x", "y"), list(itertools.product(COLUMNS, repeat=2)))
def test_frame_matches_from_records(x, y):
    """Dtypes included, whichever kinds the columns hold, step after step."""
    records = [
        AgentRows(0.0, [1, 2, 3], [COLUMNS[x], COLUMNS[y]]),
        AgentRows(1.0, [3, 1, 2], [COLUMNS[y], COLUMNS[x]]),
        AgentRows(2.0, [], [[], []]),
        AgentRows(3.0, [7], [COLUMNS[x][:1], COLUMNS[y][:1]]),
    ]
    cache = FrameCache()
    for done in range(1, len(records) + 1):
        expected = from_rows(records[:done], ["x", "y"])
        assert_same(expected, records_frame(records[:done], ["x", "y"]))
        assert_same(expected, growing_frame(cache, records[:done], ["x", "y"]))


def test_growing_frame_rebuilds_when_its_records_change():
    """A reset, a replaced step or new names rebuild; altering a result changes nothing."""
    first, second = AgentRows(0.0, [1], [[1]]), AgentRows(1.0, [1], [[2]])
    cache = FrameCache()
    frame = growing_frame(cache, [first, second], ["x"])
    frame.iloc[0, 0] = 99
    assert_same(
        from_rows([first, second], ["x"]), growing_frame(cache, [first, second], ["x"])
    )
    replaced = [(1.0, 1, 5)]
    assert_same(
        from_rows([first, replaced], ["x"]),
        growing_frame(cache, [first, replaced], ["x"]),
    )
    assert_same(from_rows([second], ["x"]), growing_frame(cache, [second], ["x"]))
    assert_same(from_rows([first], ["y"]), growing_frame(cache, [first], ["y"]))
    assert pickle.loads(pickle.dumps(cache)).records == []  # noqa: S301


def test_collector_frame_equals_a_fresh_build_at_every_call():
    """The cached agent frame equals a fresh collector's, then survives a reset."""

    class Walker(Agent):
        def __init__(self, model):
            super().__init__(model)
            self.value = 0

    model = Model(rng=1)
    agents = [Walker(model) for _ in range(3)]
    collector = DataCollector(agent_reporters={"value": "value"})
    for step in range(5):
        for agent in agents:
            agent.value += step * 0.5
        model.time += 1
        collector.collect(model)
        fresh = DataCollector(agent_reporters={"value": "value"})
        fresh._agent_records = dict(collector._agent_records)
        assert_same(
            fresh.get_agent_vars_dataframe(), collector.get_agent_vars_dataframe()
        )
    collector._agent_records.clear()
    collector.collect(model)
    assert len(collector.get_agent_vars_dataframe()) == len(agents)
