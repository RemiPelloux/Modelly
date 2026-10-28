"""Tests for the Python half of the browser runner, run in CPython."""

import enum
import json
from typing import Literal

import pytest

from modelly.core.model import Model
from modelly.scenarios import Scenario
from modelly.studio.params import parameters_of
from modelly.web.runtime import (
    NATIVE_MODULES,
    BrowserRun,
    decode_value,
    describe,
    encode_parameter,
    native_modules,
)

BOLTZMANN = "modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"
SEED = 7
STOP_AFTER = 3


class Colour(enum.Enum):
    """A choice by Enum."""

    RED = "red"
    BLUE = "blue"


class Fields(Scenario):
    """One field of every kind the page encodes."""

    flag: bool = True
    count: int = 3
    rate: float = 0.25
    mode: Literal["x", "y"] = "y"
    colour: Colour = Colour.BLUE
    shape: tuple = (1, 2)


class FieldsModel(Model):
    """A model that keeps its scenario."""

    def __init__(self, scenario: Fields = Fields):
        """Build from ``scenario``."""
        super().__init__(scenario=scenario)


class Stops(Model):
    """A model that stops after its third step."""

    calls = 0

    def step(self):
        """Stop at three steps."""
        self.calls += 1
        self.running = self.calls < STOP_AFTER


def fields():
    """The panel's fields of FieldsModel, by name."""
    return {p.name: p for p in parameters_of(FieldsModel)}


def test_encode_choices_as_indices_and_fixed_as_repr():
    """A choice sends the index of its default; a fixed field its repr."""
    encoded = {d["name"]: d for d in describe(FieldsModel)}
    assert encoded["colour"] == {
        "name": "colour",
        "kind": "choice",
        "default": 1,
        "choices": ["RED", "BLUE"],
    }
    assert encoded["mode"]["default"] == 1
    assert encoded["shape"]["kind"] == "fixed"
    assert encoded["shape"]["default"] == "(1, 2)"
    assert encoded["rate"]["kind"] == "fraction"
    json.dumps(list(encoded.values()))  # the page reads it as JSON


def test_decode_values_the_page_sends():
    """Indices become the choices, numbers and flags their Python types."""
    by_name = fields()
    assert decode_value(by_name["colour"], 0) is Colour.RED
    assert decode_value(by_name["mode"], "0") == "x"
    assert decode_value(by_name["count"], 4.0) == 4
    assert isinstance(decode_value(by_name["count"], 4.0), int)
    assert decode_value(by_name["rate"], "0.5") == 0.5
    assert decode_value(by_name["flag"], 0) is False
    assert encode_parameter(by_name["count"])["default"] == 3


def test_build_advance_and_state():
    """A run reports its steps, the new reporter rows only and the agents' cells."""
    run = BrowserRun(BOLTZMANN)
    run.build(json.dumps({"n": 20, "width": 5, "height": 5}), SEED)
    first = json.loads(run.state_json())
    assert first["steps"] == 0
    assert first["space"]["cells"]
    assert first["space"]["bounds"] == [0.0, 0.0, 5.0, 5.0]
    assert len(first["space"]["points"]) == 20
    assert run.advance(3) == 3
    state = json.loads(run.state_json("wealth"))
    assert state["steps"] == 3
    assert {len(rows) for rows in state["series"].values()} == {3}
    assert "wealth" in state["attributes"]
    assert all(isinstance(point[2], float) for point in state["space"]["points"])


def test_build_ignores_fixed_and_unknown_fields():
    """Only editable fields reach the model; the seed seeds it."""
    run = BrowserRun("tests.web.test_runtime:FieldsModel")
    run.build(json.dumps({"colour": 0, "shape": "(9,)", "nope": 1}), SEED)
    # The target imports this file again as tests.web.test_runtime: compare by name.
    assert run.model.scenario.colour.name == "RED"
    assert run.model.scenario.shape == (1, 2)


def test_advance_stops_with_the_model_and_the_budget():
    """No step after running turns False; a zero budget allows one step per call."""
    run = BrowserRun("tests.web.test_runtime:Stops")
    run.build("{}", SEED)
    assert run.advance(1, budget_s=0) == 1
    assert run.advance(10) == 2
    assert run.advance(10) == 0
    assert json.loads(run.state_json())["running"] is False


def test_unknown_target_is_a_target_error():
    """A model that does not exist fails the way Studio's loader fails."""
    with pytest.raises(ValueError, match="not a Model subclass"):
        BrowserRun("tests.web.test_runtime:Colour")


def test_native_modules_are_known_names():
    """The compiled modules found are among the four Modelly ships."""
    assert set(native_modules()) <= set(NATIVE_MODULES)
