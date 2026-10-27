"""Tests for the xarray export of the DataCollector (xarray is optional: those tests skip)."""

import sys

import numpy as np
import pytest

from modelly import Agent, Model
from modelly.data.collector import DataCollector
from modelly.data.xarray_export import stacked, to_xarray

SIDE = 3
STEPS = 4


class Heater(Agent):
    """An agent whose value grows by its id each step."""

    def __init__(self, model):
        """Start at zero."""
        super().__init__(model)
        self.value = 0

    def step(self):
        """Grow by the agent's id."""
        self.value += self.unique_id


class Room(Model):
    """Two agents, a total and a grid that warms up each step."""

    def __init__(self):
        """Create the agents and the collector."""
        super().__init__(rng=1)
        Heater.create_agents(self, 2)
        self.heat = np.zeros((SIDE, SIDE))
        self.datacollector = DataCollector(
            model_reporters={
                "total": lambda m: sum(a.value for a in m.agents),
                "heat": "heat",
            },
            agent_reporters={"value": "value"},
        )
        self.datacollector.collect(self)

    def step(self):
        """Every agent acts, the grid warms, the data is recorded."""
        self.agents.do("step")
        self.heat = self.heat + 1
        self.datacollector.collect(self)


def collected() -> DataCollector:
    """A collector after STEPS steps."""
    model = Room()
    model.run_for(STEPS)
    return model.datacollector


def test_missing_xarray_names_the_extra(monkeypatch):
    """Without xarray, every kind raises an ImportError that says what to install."""
    monkeypatch.setitem(sys.modules, "xarray", None)
    collector = collected()
    for kind in ("model", "agent"):
        with pytest.raises(ImportError, match=r"modelly-abm\[xarray\]"):
            collector.to_xarray(kind)


def test_stacked_shapes_and_dimension_names():
    """Numbers give a series, equal arrays a stack, ragged ones one object per step."""
    assert stacked("n", [1, 2, 3], None)[0] == ("time",)
    dims, array = stacked("heat", [np.zeros((2, 3))] * 4, None)
    assert dims == ("time", "heat_dim0", "heat_dim1") and array.shape == (4, 2, 3)
    assert stacked("heat", [np.zeros((2, 3))], ("x", "y"))[0] == ("time", "x", "y")
    dims, array = stacked("bins", [np.zeros(2), np.zeros(3)], None)
    assert dims == ("time",) and array.dtype == object
    with pytest.raises(ValueError, match="dimension"):
        stacked("heat", [np.zeros((2, 3))], ("x",))


def test_bad_kind_and_missing_name():
    """An unknown kind and an agenttype without its class are usage errors."""
    collector = collected()
    with pytest.raises(ValueError, match="kind must be"):
        to_xarray(collector, "nope")
    with pytest.raises(ValueError, match="needs name"):
        to_xarray(collector, "agenttype")


def test_model_and_agent_datasets_line_up():
    """The model dataset stacks the grid over time; the agent one is a (time, AgentID) panel."""
    xr = pytest.importorskip("xarray")
    collector = collected()
    model = collector.to_xarray(dims={"heat": ("x", "y")})
    assert model["heat"].dims == ("time", "x", "y")
    assert model.sizes["time"] == STEPS + 1
    assert float(model["heat"].isel(time=-1).mean()) == STEPS
    agents = collector.to_xarray("agent")
    assert agents["value"].dims == ("time", "AgentID")
    assert list(agents["time"].values) == list(model["time"].values)
    merged = xr.merge([model, agents])
    assert set(merged.data_vars) == {"total", "heat", "value"}
