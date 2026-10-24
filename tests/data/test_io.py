"""Tests for the Arrow and Parquet export of the DataCollector and the DuckDB helper."""

import pytest

from modelly import Agent, Model
from modelly._optional import require
from modelly.data.collector import DataCollector
from modelly.data.io import query, tables_of, to_arrow, to_parquet

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")
pytest.importorskip("duckdb")


class Walker(Agent):
    """An agent whose value grows by its id each step."""

    def __init__(self, model):  # noqa: D107
        super().__init__(model)
        self.value = 0

    def step(self):  # noqa: D102
        self.value += self.unique_id


class Walk(Model):
    """Three walkers, with model, agent and table data."""

    def __init__(self):  # noqa: D107
        super().__init__(rng=1)
        Walker.create_agents(self, 3)
        self.datacollector = DataCollector(
            model_reporters={"total": lambda m: sum(a.value for a in m.agents)},
            agent_reporters={"value": "value"},
            agenttype_reporters={Walker: {"double": lambda a: 2 * a.value}},
            tables={"events": ["step", "note"]},
        )

    def step(self):  # noqa: D102
        self.agents.do("step")
        self.datacollector.collect(self)
        self.datacollector.add_table_row("events", {"step": self.time, "note": "ok"})


@pytest.fixture
def collector():
    """A collector after three steps."""
    model = Walk()
    model.run_for(3)
    return model.datacollector


def test_model_table_matches_dataframe(collector):
    """to_arrow('model') holds the model DataFrame's values."""
    table = collector.to_arrow()
    assert table.column("total").to_pylist() == list(
        collector.get_model_vars_dataframe()["total"]
    )


def test_agent_table_has_index_columns(collector):
    """Agent rows keep Step and AgentID as columns."""
    table = to_arrow(collector, "agent")
    assert table.column_names == ["Step", "AgentID", "value"]
    assert table.num_rows == 9


def test_agenttype_and_table_kinds(collector):
    """The agenttype and table kinds need a name and export their rows."""
    assert to_arrow(collector, "agenttype", Walker).num_rows == 9
    assert (
        to_arrow(collector, "table", "events").column("note").to_pylist() == ["ok"] * 3
    )
    for kind in ("agenttype", "table"):
        with pytest.raises(ValueError, match="needs name"):
            to_arrow(collector, kind)
    with pytest.raises(ValueError, match="kind must be"):
        to_arrow(collector, "nope")


def test_parquet_round_trip_leaves_no_temp_file(collector, tmp_path):
    """to_parquet writes the file atomically: no temporary file is left behind."""
    path = collector.to_parquet(tmp_path / "out" / "agents.parquet", kind="agent")
    assert pq.read_table(path).equals(to_arrow(collector, "agent"))
    assert [p.name for p in path.parent.iterdir()] == ["agents.parquet"]
    to_parquet(collector, path)  # overwriting is atomic too
    assert pq.read_table(path).column_names == ["total"]


def test_query_over_tables_and_files(collector, tmp_path):
    """The query helper reads Arrow tables, DataFrames and Parquet globs by name."""
    to_parquet(collector, tmp_path / "a.parquet", "agent")
    to_parquet(collector, tmp_path / "b.parquet", "agent")
    files = query("SELECT count(*) FROM runs", runs=tmp_path / "*.parquet")
    assert files.fetchall()[0][0] == 18
    frames = query(
        "SELECT max(total) FROM model", model=collector.get_model_vars_dataframe()
    )
    assert frames.fetchall()[0][0] == 18
    assert set(tables_of(collector)) == {"model", "agent", "events"}


def test_missing_dependency_names_the_extra():
    """An absent optional module raises an ImportError naming the extra."""
    with pytest.raises(ImportError, match=r"modelly-abm\[experiments\]"):
        require("modelly_not_installed_module", "experiments")
