"""Tests for finding a model's DataCollector and writing its tables to disk."""

import pandas as pd
import pytest

from modelly import Agent, Model
from modelly.data.collector import DataCollector
from modelly.provenance import outputs
from modelly.provenance.outputs import (
    CSV,
    PARQUET,
    collected_tables,
    find_collector,
    read_table,
    write_table,
    write_tables,
)


class Sheep(Agent):
    """An agent with an energy attribute."""

    def __init__(self, model, energy):
        """Create the instance."""
        super().__init__(model)
        self.energy = energy


def _collector_model(attribute="datacollector"):
    model = Model(rng=4)
    for energy in (3, 5):
        Sheep(model, energy)
    model.grass = 10
    collector = DataCollector(
        model_reporters={"Grass": "grass"},
        agent_reporters={"Energy": "energy"},
        agenttype_reporters={Sheep: {"E": "energy"}},
        tables={"Deaths": ["unique_id", "age"]},
    )
    collector.collect(model)
    collector.add_table_row("Deaths", {"unique_id": 9, "age": 4})
    setattr(model, attribute, collector)
    return model, collector


def test_find_collector_prefers_datacollector_attribute():
    """Find collector prefers datacollector attribute."""
    model, collector = _collector_model()
    model.other = DataCollector()
    assert find_collector(model) is collector


def test_find_collector_falls_back_to_any_attribute():
    """Find collector falls back to any attribute."""
    model, collector = _collector_model("recorder")
    assert find_collector(model) is collector


def test_find_collector_none():
    """Find collector none."""
    model = Model(rng=1)
    model.datacollector = "not a collector"
    assert find_collector(model) is None
    assert collected_tables(model) == {}


def test_collected_tables_flattens_every_table():
    """Collected tables flattens every table."""
    model, _ = _collector_model()
    tables = collected_tables(model)
    assert sorted(tables) == ["agents", "agents_Sheep", "model", "table_Deaths"]
    assert list(tables["model"].columns) == ["Grass"]
    assert tables["model"]["Grass"].tolist() == [10]
    assert {"Step", "AgentID", "Energy"} <= set(tables["agents"].columns)
    assert sorted(tables["agents"]["Energy"]) == [3, 5]
    assert tables["table_Deaths"].to_dict("records") == [{"unique_id": 9, "age": 4}]
    for frame in tables.values():
        assert isinstance(frame.index, pd.RangeIndex)


def test_collected_tables_skips_empty_reporters():
    """Collected tables skips empty reporters."""
    model = Model(rng=1)
    model.datacollector = DataCollector()
    assert collected_tables(model) == {}


@pytest.mark.parametrize("form", [CSV, PARQUET])
def test_write_and_read_round_trip(tmp_path, form):
    """Write and read round trip."""
    if form == PARQUET:
        pytest.importorskip("pyarrow")
    frame = pd.DataFrame({"a": [1, 2], "b": ["x", "é"]})
    record = write_table(frame, tmp_path, "model", form)
    path = tmp_path / f"model.{form}"
    assert path.exists()
    assert record["format"] == form
    assert record["path"] == path.name
    assert record["rows"] == 2
    assert record["columns"] == ["a", "b"]
    assert record["table"] == "model"
    assert len(record["hash"]) >= 32
    pd.testing.assert_frame_equal(read_table(path, form), frame)


def test_csv_is_utf8_with_unix_newlines(tmp_path):
    """Csv is utf8 with unix newlines."""
    write_table(pd.DataFrame({"name": ["é"]}), tmp_path, "t", CSV)
    assert (tmp_path / "t.csv").read_bytes() == "name\né\n".encode()


def test_default_format_follows_pyarrow_availability(tmp_path, monkeypatch):
    """Default format follows pyarrow availability."""
    monkeypatch.setattr(outputs, "parquet_available", lambda: False)
    assert write_table(pd.DataFrame({"a": [1]}), tmp_path, "t", None)["format"] == CSV


def test_parquet_failure_falls_back_to_csv(tmp_path, monkeypatch):
    """Parquet failure falls back to csv."""

    def broken(self, *args, **kwargs):
        raise TypeError("cannot store this column")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", broken)
    record = write_table(pd.DataFrame({"a": [1]}), tmp_path, "t", PARQUET)
    assert record["format"] == CSV
    assert (tmp_path / "t.csv").exists()
    assert not (tmp_path / "t.parquet").exists()


def test_csv_errors_are_not_swallowed(tmp_path, monkeypatch):
    """Csv errors are not swallowed."""

    def broken(self, *args, **kwargs):
        raise ValueError("bad csv")

    monkeypatch.setattr(pd.DataFrame, "to_csv", broken)
    with pytest.raises(ValueError, match="bad csv"):
        write_table(pd.DataFrame({"a": [1]}), tmp_path, "t", CSV)


def test_write_tables_sorted_and_reuses_forms(tmp_path):
    """Write tables sorted and reuses forms."""
    tables = {"zeta": pd.DataFrame({"a": [1]}), "alpha": pd.DataFrame({"b": [2]})}
    records = write_tables(tables, tmp_path, forms={"zeta": CSV, "alpha": CSV})
    assert [r["table"] for r in records] == ["alpha", "zeta"]
    assert all(r["format"] == CSV for r in records)
