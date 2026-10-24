"""Iterative proportional fitting and synthetic populations from marginals."""

import numpy as np
import pytest

pytest.importorskip("geopandas")

from modelly import Model
from modelly.space.geo import (
    GeoAgent,
    GeoSpace,
    ipf,
    synthesize_population,
)

CATEGORIES = {"age": ["child", "adult", "senior"], "sex": ["f", "m"]}
MARGINALS = {
    "r0": {"age": [20, 60, 20], "sex": [52, 48]},
    "r4": {"age": [5, 10, 5], "sex": [10, 10]},
}


def test_ipf_matches_marginals_and_keeps_zeros():
    """The fit meets every marginal and leaves structural zeros at zero."""
    seed = np.ones((3, 2, 2))
    seed[0, :, 1] = 0.0  # no child with the third attribute's second level
    marginals = [[30, 50, 20], [60, 40], [70, 30]]
    fitted = ipf(seed, marginals)
    for axis, target in enumerate(marginals):
        others = tuple(a for a in range(3) if a != axis)
        np.testing.assert_allclose(fitted.sum(axis=others), target, atol=1e-6)
    assert (fitted[0, :, 1] == 0).all()


def test_ipf_independence_from_uniform_seed():
    """From a uniform seed the fit is the product of the marginals over the total."""
    fitted = ipf(np.ones((2, 2)), [[30, 70], [40, 60]])
    np.testing.assert_allclose(fitted, np.outer([30, 70], [40, 60]) / 100)


def test_ipf_rejects_inconsistent_marginals():
    """Wrong counts, wrong level numbers and different totals are errors."""
    with pytest.raises(ValueError):
        ipf(np.ones((2, 2)), [[1, 1]])
    with pytest.raises(ValueError):
        ipf(np.ones((2, 2)), [[1, 1, 1], [1, 2]])
    with pytest.raises(ValueError):
        ipf(np.ones((2, 2)), [[1, 1], [1, 2]])


def test_synthesize_population_per_region():
    """Each region gets its total and first-attribute counts; seeded draws repeat."""
    people = synthesize_population(CATEGORIES, MARGINALS, np.random.default_rng(5))
    assert list(people.columns) == ["region", "age", "sex"]
    assert people.region.value_counts().to_dict() == {"r0": 100, "r4": 20}
    r4 = people[people.region == "r4"]
    assert r4.age.value_counts().to_dict() == {"adult": 10, "child": 5, "senior": 5}
    again = synthesize_population(CATEGORIES, MARGINALS, np.random.default_rng(5))
    assert people.equals(again)
    levels = len(CATEGORIES["age"])
    for region, margins in MARGINALS.items():
        sexes = people[people.region == region].sex.value_counts()
        for sex, target in zip(CATEGORIES["sex"], margins["sex"]):
            assert abs(sexes.get(sex, 0) - target) < levels
    assert synthesize_population(CATEGORIES, {}, np.random.default_rng(5)).empty


def test_population_initialises_agents(city_regions):
    """One agent per synthetic person, standing inside their region."""
    model = Model(rng=3)
    space = GeoSpace(city_regions, random=model.random)
    people = synthesize_population(CATEGORIES, MARGINALS, model.rng)
    for region, group in people.groupby("region"):
        points = space.random_points(region, len(group), model.rng)
        for point, age in zip(points, group.age):
            GeoAgent(space, model, point).age = age
    assert space.region_counts()[["r0", "r4"]].tolist() == [100, 20]
