"""A synthetic population of a real region: marginals, households, places, an epidemic.

The region is the 41 census tracts of Chittenden County, Vermont (bundled boundaries,
public domain). The marginal tables are illustrative, drawn from a seeded generator:
no real counts and no personal data. The population fits them within the rounding
tolerance, and the age-structured SEIR zoo model runs on it.
"""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("geopandas")

from modelly import Model
from modelly.population import (
    HouseholdSpec,
    PlaceSpec,
    assign_households,
    assign_places,
    contact_network,
    locate_households,
    marginal_errors,
    synthesize_population,
)
from modelly.space.geo import GeoSpace
from modelly.space.geo.samples import sample_neighbourhoods
from modelly.space.networks import contact_matrix
from modelly.zoo.age_seir.model import AgeSEIR, State, scenario_from_population

AGES = ("0-17", "18-64", "65+")
CATEGORIES = {"age": list(AGES), "sex": ["f", "m"]}
HOUSEHOLD_SHARES = [0.28, 0.34, 0.16, 0.14, 0.08]  # illustrative, 1 to 5 members
PEOPLE_PER_TRACT = (300, 700)
AGE_MIX = (20, 60, 20)  # Dirichlet weights of the illustrative age shares
SCHOOL_EVERY = 4  # one school at every fourth tract centroid
SEATS = 600
SCHOOL_REACH = 15_000.0  # metres
WORK_REACH = 20_000.0
EPIDEMIC_STEPS = 600
FINAL_SIZE_TOLERANCE = 0.05  # about five standard deviations for groups of ~4,000


def illustrative_marginals(tracts, seed=3):
    """Per tract, a total and its age and sex counts, drawn at random (not census data)."""
    rng = np.random.default_rng(seed)
    marginals = {}
    for tract in tracts.index:
        total = int(rng.integers(*PEOPLE_PER_TRACT))
        ages = np.round(rng.dirichlet(AGE_MIX) * total).astype(int)
        ages[1] += total - ages.sum()
        women = int(rng.binomial(total, 0.5))
        marginals[tract] = {"age": ages.tolist(), "sex": [women, total - women]}
    return marginals


@pytest.fixture(scope="module")
def region():
    """The tracts, their GeoSpace, the marginals and the synthetic people."""
    tracts = sample_neighbourhoods()
    model = Model(rng=7)
    space = GeoSpace(tracts, random=model.random)
    marginals = illustrative_marginals(tracts)
    people = synthesize_population(CATEGORIES, marginals, model.rng)
    spec = HouseholdSpec(dict.fromkeys(tracts.index, HOUSEHOLD_SHARES), AGES[1:])
    people = assign_households(people, spec, model.rng)
    people = locate_households(people, space, model.rng)
    centres = tracts.to_crs(space.crs).geometry.centroid
    sites = pd.DataFrame({"x": centres.x, "y": centres.y, "capacity": SEATS})
    schools = sites.iloc[::SCHOOL_EVERY].reset_index(drop=True)
    people = assign_places(
        people,
        schools,
        PlaceSpec("school", AGES[:1], max_distance=SCHOOL_REACH),
        model.rng,
    )
    people = assign_places(
        people, sites, PlaceSpec("work", AGES[1:2], max_distance=WORK_REACH), model.rng
    )
    return {"model": model, "marginals": marginals, "people": people, "sites": sites}


def test_population_reproduces_its_marginals(region):
    """Totals and ages are exact per tract; sex is within the rounding tolerance."""
    errors = marginal_errors(region["people"], region["marginals"], CATEGORIES)
    assert len(errors) == 41 * (len(AGES) + 2)
    assert (errors[errors.attribute == "age"].error == 0).all()
    assert (errors.error.abs() < len(AGES)).all()
    total = sum(sum(m["age"]) for m in region["marginals"].values())
    assert len(region["people"]) == total
    sexes = errors[errors.attribute == "sex"]
    assert sexes.error.abs().sum() / total < 0.01


def test_households_follow_the_size_table(region):
    """Every household lies in one tract, at one point, with an adult; sizes fit."""
    people = region["people"]
    households = people.groupby("household")
    assert (households.region.nunique() == 1).all()
    assert (households[["x", "y"]].nunique() == 1).all().all()
    assert people.age.isin(AGES[1:]).groupby(people.household).any().all()
    sizes = households.size()
    shares = sizes.value_counts(normalize=True).sort_index().to_numpy()
    np.testing.assert_allclose(shares, HOUSEHOLD_SHARES, atol=0.02)


def test_places_respect_capacity_and_reach(region):
    """No place over capacity; nobody beyond the distance limit; adults not at school."""
    people, sites = region["people"], region["sites"]
    for column, reach, places in (
        ("school", SCHOOL_REACH, sites.iloc[::SCHOOL_EVERY].reset_index(drop=True)),
        ("work", WORK_REACH, sites),
    ):
        placed = people[people[column] >= 0]
        assert (placed[column].value_counts() <= SEATS).all()
        target = places.iloc[placed[column]]
        distance = np.hypot(
            placed.x - target.x.to_numpy(), placed.y - target.y.to_numpy()
        )
        assert (distance <= reach).all()
    assert (people[people.age != AGES[0]].school == -1).all()
    assert (people[people.age == AGES[0]].school >= 0).mean() > 0.9


def test_age_seir_starts_from_the_population(region):
    """Group sizes and contacts come from the people; the final-size relation holds."""
    people, model = region["people"], region["model"]
    network = contact_network(people, model.rng)
    scenario = scenario_from_population(
        people, network, AGES, rng=5, steps=EPIDEMIC_STEPS
    )
    counts = people.age.value_counts()
    assert scenario.group_sizes == tuple(int(counts[a]) for a in AGES)
    groups = pd.Categorical(people.age, categories=AGES).codes
    np.testing.assert_allclose(scenario.contacts, contact_matrix(network, groups))
    seir = AgeSEIR(scenario)
    seir.run()
    assert seir.counts()[:, [State.E, State.I]].sum() == 0
    assert seir.r0() > 1
    np.testing.assert_allclose(
        seir.attack_rate(), seir.final_size(), atol=FINAL_SIZE_TOLERANCE
    )


def test_scenario_from_population_rejects_an_empty_group(region):
    """An age level with nobody in it cannot be a group of the SEIR model."""
    people = region["people"]
    network = contact_network(people.iloc[:0], np.random.default_rng(1))
    with pytest.raises(ValueError, match="age level"):
        scenario_from_population(people.iloc[:0], network, AGES)
