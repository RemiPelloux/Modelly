"""Truncate-replicate-sample rounding, marginal checks and the old geo import path."""

import numpy as np
import pytest

from modelly._deprecation import ModellyDeprecationWarning
from modelly.population import ipf, marginal_errors, synthesize_population, trs
from modelly.population.fitting import REGION, TOLERANCE

CATEGORIES = {"age": ["0-17", "18-64", "65+"], "sex": ["f", "m"]}
MARGINALS = {
    "a": {"age": [30, 50, 20], "sex": [52, 48]},
    "b": {"age": [10, 25, 5], "sex": [20, 20]},
}


def test_trs_keeps_the_total_and_stays_within_one():
    """Every count is the floor or the ceiling of its expectation; the total is exact."""
    expected = np.array([[2.4, 0.3], [1.3, 5.0]])
    counts = trs(expected, np.random.default_rng(1))
    assert counts.shape == (4,)
    assert counts.sum() == 9
    assert np.all(np.abs(counts - expected.ravel()) < 1)
    assert counts[3] == 5  # a whole number is never rounded away


def test_trs_follows_the_fractions_on_average():
    """Over many draws the remainder lands in proportion to the fractional parts."""
    expected = np.array([0.2, 0.3, 0.5])
    rng = np.random.default_rng(2)
    draws = np.array([trs(expected, rng) for _ in range(4000)])
    np.testing.assert_allclose(draws.mean(axis=0), expected, atol=0.03)


def test_marginal_errors_lists_every_level():
    """One row per (region, attribute, level); the first attribute fits exactly."""
    people = synthesize_population(CATEGORIES, MARGINALS, np.random.default_rng(3))
    errors = marginal_errors(people, MARGINALS, CATEGORIES)
    assert len(errors) == 2 * (3 + 2)
    assert list(errors.columns) == [
        REGION,
        "attribute",
        "level",
        "target",
        "synthetic",
        "error",
    ]
    ages = errors[errors.attribute == "age"]
    assert (ages.error == 0).all()
    assert (errors.error.abs() < len(CATEGORIES["age"])).all()


def test_geo_population_names_still_work_and_warn():
    """The 1.3 names keep working until 2.0, each warning with its new home."""
    pytest.importorskip("geopandas")
    from modelly.space import geo  # noqa: PLC0415
    from modelly.space.geo import population  # noqa: PLC0415

    with pytest.warns(ModellyDeprecationWarning, match=r"modelly\.population\.ipf"):
        assert geo.ipf is ipf
    with pytest.warns(ModellyDeprecationWarning, match="2.0"):
        assert population.synthesize_population is synthesize_population
    with pytest.warns(ModellyDeprecationWarning, match=r"fitting\.TOLERANCE"):
        assert population.TOLERANCE == TOLERANCE
    with pytest.raises(AttributeError, match="no_such_name"):
        _ = geo.no_such_name
