"""Tests for what the browser runner draws: agents in space and reporter series."""

import math

from modelly.core.agent import Agent
from modelly.core.model import Model
from modelly.data import DataCollector
from modelly.examples.basic.boid_flockers.model import BoidFlockers, BoidsScenario
from modelly.examples.basic.virus_on_network.model import VirusOnNetwork
from modelly.web import snapshot
from modelly.web.snapshot import colour_attributes, series_rows, space_view

SEED = 3


class Plain(Agent):
    """An agent without a place, with one number and one text."""

    def __init__(self, model):
        """A score of one half and a label."""
        super().__init__(model)
        self.score = 0.5
        self.label = "a"


class Placeless(Model):
    """Agents with no space and a reporter that is not a number."""

    def __init__(self, n=3):
        """``n`` plain agents; one numeric and one text reporter."""
        super().__init__(rng=SEED)
        for _ in range(n):
            Plain(self)
        self.datacollector = DataCollector(
            {"count": lambda m: len(m.agents), "name": lambda m: "x"}
        )
        self.datacollector.collect(self)


def test_continuous_space_bounds_and_dots():
    """Boids are dots inside the space's bounds, as floats."""
    model = BoidFlockers(BoidsScenario(rng=SEED, population_size=10))
    view = space_view(model)
    assert not view["cells"]
    assert all(isinstance(v, float) for v in view["bounds"])
    assert view["classes"] == ["Boid"]
    x0, y0, x1, y1 = view["bounds"]
    assert all(x0 <= x <= x1 and y0 <= y <= y1 for x, y, _ in view["points"])


def test_network_places_agents_on_the_layout():
    """Network agents take their node's layout position; no bounds are given."""
    model = VirusOnNetwork(num_nodes=8, rng=SEED)
    view = space_view(model)
    assert view["bounds"] is None
    assert len(view["points"]) == 8


def test_no_place_no_view_and_numeric_series_only():
    """Agents without a place give no view; text reporters are left out."""
    model = Placeless()
    assert space_view(model) is None
    assert colour_attributes(model) == ["score"]
    assert series_rows(model) == {"count": [3.0]}
    assert series_rows(model, start=1) == {"count": []}


def test_missing_values_and_no_collector():
    """A NaN reporter row is None; a model without a collector has no series."""
    model = Placeless()
    model.datacollector = DataCollector({"gap": lambda m: math.nan})
    model.datacollector.collect(model)
    assert series_rows(model) == {"gap": [None]}
    assert series_rows(Model(rng=SEED)) is None


def test_colour_by_attribute_and_the_point_cap(monkeypatch):
    """Colouring by an attribute sends its value; at most MAX_POINTS points are sent."""
    monkeypatch.setattr(snapshot, "MAX_POINTS", 4)
    model = BoidFlockers(BoidsScenario(rng=SEED, population_size=10))
    view = space_view(model, "speed")
    assert len(view["points"]) == 4
    assert view["classes"] == []
    assert all(isinstance(value, float) for *_, value in view["points"])
    assert space_view(model, "missing")["points"][0][2] is None
