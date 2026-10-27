"""Households from a size distribution: exact sizes, one head each, people unchanged."""

import numpy as np
import pandas as pd
import pytest

from modelly.population import HouseholdSpec, assign_households, household_sizes
from modelly.population.households import HOUSEHOLD

SHARES = [0.3, 0.35, 0.15, 0.12, 0.08]
ADULTS = ("adult", "senior")


def people_of(region, children, adults, seniors):
    """A DataFrame of people in one region with the given counts per age level."""
    ages = ["child"] * children + ["adult"] * adults + ["senior"] * seniors
    return pd.DataFrame({"region": region, "age": ages})


@pytest.mark.parametrize("people", [0, 1, 7, 100, 1001])
def test_household_sizes_hold_everybody(people):
    """The sizes add up to the people, between 1 and the largest size."""
    sizes = household_sizes(people, SHARES, np.random.default_rng(people))
    assert sizes.sum() == people
    assert sizes.min(initial=1) >= 1
    assert sizes.max(initial=1) <= len(SHARES)


def test_household_sizes_follow_the_shares():
    """For a large region the size distribution is the one asked for."""
    sizes = household_sizes(100_000, SHARES, np.random.default_rng(4))
    shares = np.bincount(sizes, minlength=len(SHARES) + 1)[1:] / sizes.size
    np.testing.assert_allclose(shares, SHARES, atol=0.005)


def test_assign_households_one_head_each_and_same_people():
    """Every household is in one region and has an adult; nobody is added or lost."""
    people = pd.concat(
        [people_of("a", 30, 50, 20), people_of("b", 10, 30, 10)], ignore_index=True
    )
    spec = HouseholdSpec({"a": SHARES, "b": [0.5, 0.5]}, heads=ADULTS)
    housed = assign_households(people, spec, np.random.default_rng(5))
    assert housed.drop(columns=HOUSEHOLD).equals(people)
    assert (housed[HOUSEHOLD] >= 0).all()
    by_household = housed.groupby(HOUSEHOLD)
    assert (by_household.region.nunique() == 1).all()
    assert by_household.age.agg(lambda ages: ages.isin(ADULTS).any()).all()
    assert by_household.size().max() <= len(SHARES)
    assert housed[housed.region == "b"].groupby(HOUSEHOLD).size().max() <= 2
    again = assign_households(people, spec, np.random.default_rng(5))
    assert again.equals(housed)


def test_assign_households_needs_enough_heads():
    """A region with more households than adults is an error, not a silent fix."""
    people = people_of("a", 20, 1, 0)
    spec = HouseholdSpec({"a": [1.0]}, heads=ADULTS)
    with pytest.raises(ValueError, match="household heads"):
        assign_households(people, spec, np.random.default_rng(6))
