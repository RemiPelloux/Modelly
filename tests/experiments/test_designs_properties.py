"""Property-based tests for experiment designs: point counts and bounds."""

import math

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from modelly.experiments import ScenarioSpace, designs
from modelly.experiments.space import Range

# scipy builds a new QMC engine per call; fewer examples keep this file fast.
SAMPLED_EXAMPLES = 15
MAX_LEVELS = 6
MAX_POINTS = 32
MAX_CHOICES = 4
BOUND = 1e6

finite = st.floats(-BOUND, BOUND, allow_nan=False, allow_infinity=False)
ranges = st.tuples(finite, finite).filter(lambda b: b[0] < b[1])
int_ranges = st.tuples(st.integers(-100, 100), st.integers(-100, 100)).filter(
    lambda b: b[0] < b[1]
)
choices = st.lists(st.integers(0, 9), min_size=1, max_size=MAX_CHOICES, unique=True)
samplers = st.sampled_from([designs.latin_hypercube, designs.sobol, designs.halton])


def _space(real, whole, choice):
    return ScenarioSpace(beta=real, n=whole, policy=choice, fixed_value=7)


def _within(point, real, whole, choice):
    assert real[0] <= point["beta"] <= real[1]
    assert whole[0] <= point["n"] <= whole[1] and isinstance(point["n"], int)
    assert point["policy"] in choice
    assert point["fixed_value"] == 7


@given(real=ranges, whole=int_ranges, choice=choices, levels=st.integers(1, MAX_LEVELS))
def test_full_factorial_count_and_bounds(real, whole, choice, levels):
    """One point per combination of levels, each inside its dimension."""
    space = _space(real, whole, choice)
    points = designs.full_factorial(levels=levels).points(space)
    integer_levels = len(Range(*whole, integer=True).levels(levels))
    assert len(points) == levels * integer_levels * len(choice)
    for point in points:
        _within(point, real, whole, choice)


@given(
    real=ranges,
    whole=int_ranges,
    choice=choices,
    n=st.integers(1, MAX_POINTS),
    make=samplers,
    seed=st.integers(0, 2**32 - 1),
)
@settings(max_examples=SAMPLED_EXAMPLES)
@pytest.mark.filterwarnings("ignore:The balance properties of Sobol:UserWarning")
def test_sampled_designs_count_bounds_and_seed(real, whole, choice, n, make, seed):
    """Exactly n points inside the space; the same seed gives the same points."""
    space = _space(real, whole, choice)
    first = make(n).points(space, np.random.default_rng(seed))
    again = make(n).points(space, np.random.default_rng(seed))
    assert len(first) == n
    assert first == again
    for point in first:
        _within(point, real, whole, choice)


@given(
    low=st.floats(1e-6, 1e3),
    factor=st.floats(1.5, 1e3),
    u=st.floats(0.0, 1.0, exclude_max=True),
)
def test_log_range_stays_inside_its_bounds(low, factor, u):
    """A log-scale value is inside [low, high] (up to rounding of exp and log)."""
    high = low * factor
    assume(math.isfinite(high))
    value = Range(low, high, log=True).from_unit(u)
    assert low * (1 - 1e-12) <= value <= high * (1 + 1e-12)
