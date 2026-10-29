"""The Parquet recorder writes a growing file in linear time; JSON gives one row per agent."""

import pandas as pd
import pytest

from modelly.core.agent import Agent
from modelly.core.model import Model
from modelly.data.recorders import (
    DataRecorder,
    DatasetConfig,
    JSONDataRecorder,
    ParquetDataRecorder,
)

AGENTS = 20
STEPS = 200


class Walker(Agent):
    """An agent whose value changes every step."""

    def __init__(self, model, value):
        """Start at value."""
        super().__init__(model)
        self.value = value
        self.other = value * 2.0


class Walkers(Model):
    """Tracks the model, a numpy dataset and a list dataset."""

    def __init__(self, n=AGENTS):
        """Create n walkers."""
        super().__init__(rng=1)
        self.model_val = 0
        self.data_registry.track_model(self, "model_data", fields=["model_val"])
        self.data_registry.track_agents_numpy(
            Walker, "numpy_data", fields=["value", "other"], n=n, dtype=float
        )
        walkers = Walker.create_agents(self, n, [float(i) for i in range(n)])
        self.data_registry.track_agents(walkers, "agent_data", fields=["value"])

    def step(self):
        """Change every value."""
        self.model_val += 1
        for walker in self.agents:
            walker.value += 1.0


CONFIG = {"model_data": {}, "numpy_data": {}, "agent_data": {}}


def test_parquet_writes_grow_with_the_file_so_their_number_is_logarithmic(
    tmp_path, monkeypatch
):
    """A fixed buffer rewrote the file every few steps (quadratic); now writes double."""
    pytest.importorskip("pyarrow")
    writes = []
    original = pd.DataFrame.to_parquet

    def counting(self, path, *args, **kwargs):
        writes.append(len(self))
        return original(self, path, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_parquet", counting)
    model = Walkers()
    recorder = ParquetDataRecorder(model, CONFIG, output_dir=tmp_path)
    recorder.buffer_size = 1
    for _ in range(STEPS):
        model.step()
    frames = recorder.get_all_dataframes()

    assert len(frames["numpy_data"]) == AGENTS * STEPS
    assert len(frames["model_data"]) == STEPS
    # 3 datasets, each written about log2(rows) times instead of once per step
    assert len(writes) < 3 * 12


def test_parquet_matches_the_in_memory_recorder(tmp_path):
    """Same rows, same values, whatever the buffering."""
    pytest.importorskip("pyarrow")
    # One model at a time: a numpy dataset installs its fields on the agent class.
    memory_model = Walkers()
    memory = DataRecorder(memory_model, CONFIG)
    for _ in range(37):
        memory_model.step()
    expected = {n: memory.get_table_dataframe(n) for n in ("numpy_data", "model_data")}

    parquet_model = Walkers()
    parquet = ParquetDataRecorder(parquet_model, CONFIG, output_dir=tmp_path)
    parquet.buffer_size = 3
    for _ in range(37):
        parquet_model.step()

    for name, frame in expected.items():
        got = parquet.get_table_dataframe(name)[list(frame.columns)]
        pd.testing.assert_frame_equal(got, frame, check_dtype=False)


def test_parquet_summary_counts_buffered_rows(tmp_path):
    """Rows still in the buffer are counted, rows on disk come from the file footer."""
    pytest.importorskip("pyarrow")
    model = Walkers()
    recorder = ParquetDataRecorder(
        model, {"numpy_data": DatasetConfig()}, output_dir=tmp_path
    )
    recorder.buffer_size = 10**6
    for _ in range(5):
        model.step()
    assert recorder.summary()["numpy_data"]["rows"] == 5 * AGENTS

    recorder._flush_buffer("numpy_data")
    model.step()
    assert recorder.summary()["numpy_data"]["rows"] == 6 * AGENTS
    recorder.clear()
    assert recorder.summary()["numpy_data"]["rows"] == 0


def test_parquet_buffer_does_not_alias_the_live_agent_array(tmp_path):
    """A buffered numpy snapshot keeps the values of its own time."""
    pytest.importorskip("pyarrow")
    model = Walkers(n=3)
    recorder = ParquetDataRecorder(
        model, {"numpy_data": DatasetConfig()}, output_dir=tmp_path
    )
    recorder.buffer_size = 10**6
    model.step()
    model.step()
    df = recorder.get_table_dataframe("numpy_data")
    first, second = (df[df["time"] == t]["value"].tolist() for t in (0.0, 1.0))
    assert second == [v + 1.0 for v in first]


def test_json_numpy_dataset_has_one_row_per_agent(tmp_path):
    """As every other recorder: agent_id, the fields and time, one row per agent."""
    memory_model = Walkers(n=3)
    memory = DataRecorder(memory_model, {"numpy_data": DatasetConfig()})
    for _ in range(2):
        memory_model.step()
    expected = memory.get_table_dataframe("numpy_data")

    json_model = Walkers(n=3)
    recorder = JSONDataRecorder(
        json_model, {"numpy_data": DatasetConfig()}, output_dir=tmp_path
    )
    for _ in range(2):
        json_model.step()
    got = recorder.get_table_dataframe("numpy_data")
    assert list(got.columns) == ["agent_id", "value", "other", "time"]
    pd.testing.assert_frame_equal(got, expected, check_dtype=False)


def test_json_empty_list_snapshot_has_no_rows(tmp_path):
    """A snapshot of no agents adds no row (it used to add one row of an empty list)."""
    model = Model()
    model.data_registry.track_agents(model.agents, "agent_data", fields=["value"])
    recorder = JSONDataRecorder(
        model, {"agent_data": DatasetConfig()}, output_dir=tmp_path
    )
    model.step()
    assert recorder.get_table_dataframe("agent_data").empty
