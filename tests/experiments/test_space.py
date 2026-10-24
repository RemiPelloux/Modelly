"""Tests for ScenarioSpace: dimensions, the unit-cube mapping and typing against a Scenario."""

import numpy as np
import pytest

from modelly.experiments.space import Choice, Fixed, Range, ScenarioSpace, as_dimension
from tests.experiments.models import WalkScenario


def test_values_become_dimensions():
    """A tuple is a Range, a list a Choice, anything else Fixed."""
    assert as_dimension((0.1, 0.5)) == Range(0.1, 0.5)
    assert as_dimension((1, 9)) == Range(1, 9, integer=True)
    assert as_dimension(["a", "b"]) == Choice(["a", "b"])
    assert as_dimension(np.int64(3)) == Fixed(3)
    with pytest.raises(TypeError, match="low, high"):
        as_dimension((1, 2, 3))


def test_range_mapping_and_levels():
    """Ranges map [0, 1) linearly, on a log scale, or to whole numbers."""
    assert Range(0.0, 2.0).from_unit(0.25) == 0.5
    assert Range(1.0, 100.0, log=True).from_unit(0.5) == pytest.approx(10.0)
    integer = Range(1, 3, integer=True)
    assert [integer.from_unit(u) for u in (0.0, 0.4, 0.99)] == [1, 2, 3]
    assert Range(0.0, 1.0).levels(3) == [0.0, 0.5, 1.0]
    assert Range(1.0, 100.0, log=True).levels(3) == pytest.approx([1, 10, 100])
    assert Range(1, 2, integer=True).levels(5) == [1, 2]
    with pytest.raises(ValueError, match="at least 1"):
        Range(0, 1).levels(0)


def test_invalid_ranges_and_choices():
    """Empty intervals, log ranges at zero and empty choices are rejected."""
    with pytest.raises(ValueError, match="low < high"):
        Range(1.0, 1.0)
    with pytest.raises(ValueError, match="low > 0"):
        Range(0.0, 1.0, log=True)
    with pytest.raises(ValueError, match="at least one"):
        Choice([])


def test_choice_shares_the_unit_interval():
    """Each value of a Choice owns an equal share of [0, 1)."""
    choice = Choice(["a", "b", "c", "d"])
    assert [choice.from_unit(u) for u in (0.0, 0.3, 0.6, 0.999)] == list("abcd")
    assert choice.levels() == list("abcd")


def test_point_and_complete():
    """The point method maps one coordinate per dimension; complete adds the fixed values."""
    space = ScenarioSpace({"drift": (0.0, 1.0)}, policy=["a", "b"], n=7)
    assert space.names == ["drift", "policy", "n"]
    assert list(space.dimensions) == ["drift", "policy"]
    assert space.fixed == {"n": 7}
    assert space.point([0.5, 0.9]) == {"drift": 0.5, "policy": "b", "n": 7}
    assert space.complete({"drift": 0.2}) == {"drift": 0.2, "n": 7}
    with pytest.raises(ValueError, match="coordinates"):
        space.point([0.5])
    with pytest.raises(ValueError, match="not in the space"):
        space.complete({"other": 1})


def test_typed_checks_names_and_types():
    """typed() rejects unknown fields and values of the wrong type."""
    space = ScenarioSpace(drift=(0, 1), n=(5, 20), policy=["x"])
    typed = space.typed(WalkScenario)
    assert typed.parameters["n"] == Range(5, 20, integer=True)
    assert typed.parameters["drift"] == Range(0.0, 1.0)  # (0, 1) over a float field
    with pytest.raises(ValueError, match="declares no parameter"):
        ScenarioSpace(speed=(0.0, 1.0)).typed(WalkScenario)
    with pytest.raises(TypeError, match="n is int"):
        ScenarioSpace(n=(0.5, 2.5)).typed(WalkScenario)
    with pytest.raises(TypeError, match="policy is str"):
        ScenarioSpace(policy=[1, 2]).typed(WalkScenario)
    with pytest.raises(TypeError, match="fail is bool"):
        ScenarioSpace(fail=(0, 1)).typed(WalkScenario)
    assert ScenarioSpace(drift=[0, 0.5], fail=True).typed(WalkScenario)


def test_to_dict_is_json_ready():
    """to_dict describes every dimension by kind and fields."""
    described = ScenarioSpace(a=(0.0, 1.0), b=["x"], c=3).to_dict()
    assert described["a"]["kind"] == "Range"
    assert described["b"] == {"kind": "Choice", "values": ("x",)}
    assert described["c"] == {"kind": "Fixed", "value": 3}
