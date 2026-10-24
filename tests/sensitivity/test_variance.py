"""Tests for Sobol indices: Ishigami and G functions against their analytical values."""

import math

import numpy as np
import pytest

from modelly.experiments import ScenarioSpace
from modelly.sensitivity import sobol
from modelly.sensitivity.variance import indices, saltelli_sample
from tests.sensitivity.models import (
    G_COEFFICIENTS,
    g_function,
    g_indices,
    ishigami,
    ishigami_indices,
)

PI = math.pi
ISHIGAMI = ScenarioSpace(x1=(-PI, PI), x2=(-PI, PI), x3=(-PI, PI))
G_SPACE = ScenarioSpace({f"x{i}": (0.0, 1.0) for i in range(len(G_COEFFICIENTS))})


def inside(result, first, total):
    """Whether every analytical index lies in its bootstrap interval."""
    table = result.table
    s1 = (table["S1_low"] <= first) & (first <= table["S1_high"])
    st = (table["ST_low"] <= total) & (total <= table["ST_high"])
    return bool(s1.all() and st.all())


@pytest.mark.parametrize("estimator", ["jansen", "saltelli"])
def test_ishigami_matches_analytical_values(estimator):
    """S1 and ST of the Ishigami function lie within their bootstrap intervals."""
    result = sobol(ishigami, ISHIGAMI, samples=4096, seed=1, estimator=estimator)
    first, total = ishigami_indices()
    assert inside(result, first, total), result.table
    assert list(result.ranking().index) == ["x1", "x2", "x3"]
    assert result.info["evaluations"] == 4096 * 5


def test_g_function_matches_analytical_values():
    """S1 and ST of the Sobol G function lie within their bootstrap intervals."""
    result = sobol(g_function, G_SPACE, samples=2048, seed=2)
    first, total = g_indices()
    assert inside(result, first, total), result.table
    assert list(result.ranking().index[:2]) == ["x0", "x1"]


def test_same_seed_same_indices():
    """The design and the bootstrap come from the seed."""
    first = sobol(ishigami, ISHIGAMI, samples=256, seed=3).table
    second = sobol(ishigami, ISHIGAMI, samples=256, seed=3).table
    assert first.equals(second)
    assert not first.equals(sobol(ishigami, ISHIGAMI, samples=256, seed=4).table)


def test_saltelli_sample_layout():
    """[A; B; AB_i]: AB_i is A with column i from B."""
    points = saltelli_sample(2, 8, np.random.default_rng(0))
    a, b, ab0, ab1 = np.split(points, 4)
    np.testing.assert_array_equal(ab0[:, 0], b[:, 0])
    np.testing.assert_array_equal(ab0[:, 1], a[:, 1])
    np.testing.assert_array_equal(ab1[:, 1], b[:, 1])


def test_constant_output_and_errors():
    """A constant output has zero indices; bad settings are refused."""
    first, total = indices(np.ones(4), np.ones(4), np.ones((2, 4)), "jansen")
    assert first.tolist() == [0.0, 0.0] and total.tolist() == [0.0, 0.0]
    with pytest.raises(ValueError):
        sobol(ishigami, ISHIGAMI, samples=8, estimator="nope")
    with pytest.raises(ValueError):
        sobol(ishigami, ISHIGAMI, samples=8, confidence=1.5)
