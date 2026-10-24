"""Tests for the designs: sizes, bounds, stratification and determinism."""

import warnings

import numpy as np
import pytest

from modelly.experiments import ScenarioSpace, designs

SPACE = ScenarioSpace(a=(0.0, 1.0), b=(10.0, 20.0), c=["x", "y"], fixed=5)


def rng(seed=0):
    """A fresh generator."""
    return np.random.default_rng(seed)


def test_full_factorial_is_every_combination():
    """The levels of every range times every choice, the last dimension fastest."""
    points = designs.full_factorial(levels=3).points(SPACE)
    assert len(points) == 3 * 3 * 2
    assert points[0] == {"a": 0.0, "b": 10.0, "c": "x", "fixed": 5}
    assert points[1]["c"] == "y"
    per_name = designs.full_factorial(levels={"a": 2}).points(SPACE)
    assert len(per_name) == 2 * designs.DEFAULT_LEVELS * 2


def test_latin_hypercube_has_one_point_per_stratum():
    """Each range cut into n strata holds exactly one point."""
    n = 16
    points = designs.latin_hypercube(n).points(SPACE, rng())
    for name, (low, high) in (("a", (0.0, 1.0)), ("b", (10.0, 20.0))):
        strata = sorted(int((p[name] - low) / (high - low) * n) for p in points)
        assert strata == list(range(n))
    assert all(p["fixed"] == 5 and p["c"] in ("x", "y") for p in points)


@pytest.mark.parametrize(
    "make", [designs.sobol, designs.halton, designs.latin_hypercube]
)
def test_sequences_stay_in_bounds_and_repeat_by_seed(make):
    """A sampled design is inside the space, the same for a seed, different across seeds."""
    design = make(32)
    first = design.points(SPACE, rng(1))
    assert len(first) == 32
    assert all(0 <= p["a"] < 1 and 10 <= p["b"] < 20 for p in first)
    assert first == design.points(SPACE, rng(1))
    assert first != design.points(SPACE, rng(2))


def test_sobol_power_of_two_is_balanced():
    """A scrambled Sobol sample of 2^m points fills each half of every range equally."""
    points = designs.sobol(64).points(SPACE, rng(3))
    assert sum(p["a"] < 0.5 for p in points) == 32
    assert sum(p["c"] == "x" for p in points) == 32


def test_sobol_warns_off_a_power_of_two():
    """The scipy balance warning reaches the user for other sizes."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        designs.sobol(10).points(SPACE, rng())
    assert any("balance" in str(w.message) for w in caught)


def test_custom_design_completes_points():
    """Custom rows get the fixed values; names outside the space are rejected."""
    points = designs.custom([{"a": 0.3, "b": 11, "c": "y"}]).points(SPACE)
    assert points == [{"a": 0.3, "b": 11, "c": "y", "fixed": 5}]
    with pytest.raises(ValueError, match="not in the space"):
        designs.custom([{"z": 1}]).points(SPACE)
    with pytest.raises(ValueError, match="at least one"):
        designs.custom([]).points(SPACE)


def test_degenerate_designs():
    """A space of fixed values is one point; an empty sample is an error."""
    fixed = ScenarioSpace(n=3)
    assert designs.latin_hypercube(4).points(fixed) == [{"n": 3}]
    assert designs.full_factorial().points(fixed) == [{"n": 3}]
    with pytest.raises(ValueError, match="n >= 1"):
        designs.halton(0)


def test_design_descriptions():
    """to_dict names the kind and the arguments."""
    assert designs.latin_hypercube(8).to_dict() == {"kind": "latin_hypercube", "n": 8}
    assert designs.full_factorial(2).to_dict() == {
        "kind": "full_factorial",
        "levels": 2,
    }
    with pytest.raises(NotImplementedError):
        designs.Design().points(SPACE)
