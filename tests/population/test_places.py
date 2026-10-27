"""Homes in their regions; schools and workplaces nearest with room, within reach."""

import numpy as np
import pandas as pd
import pytest

from modelly.population import PlaceSpec, assign_places, locate_households
from modelly.population.places import NO_PLACE

UTM = "EPSG:32631"  # a projected CRS in metres


def pupils_on_a_line(n):
    """``n`` pupils at x = 0, 1, ..., n - 1 and one adult at the origin."""
    return pd.DataFrame(
        {
            "x": np.r_[np.arange(n, dtype=float), 0.0],
            "y": 0.0,
            "age": ["child"] * n + ["adult"],
        }
    )


def test_nearest_place_with_room_within_reach():
    """Capacity is never exceeded, nobody goes beyond the limit, adults stay out."""
    people = pupils_on_a_line(10)
    schools = pd.DataFrame({"x": [0.0, 9.0], "y": [0.0, 0.0], "capacity": [3, 3]})
    spec = PlaceSpec("school", ["child"], max_distance=4.5)
    placed = assign_places(people, schools, spec, np.random.default_rng(1))
    school = placed["school"].to_numpy()
    assert school[-1] == NO_PLACE  # the adult
    assert (np.bincount(school[school >= 0], minlength=2) <= 3).all()
    reach = np.abs(people.x.to_numpy() - schools.x.to_numpy()[school.clip(0)])
    assert (reach[school >= 0] <= 4.5).all()
    assert (school[:10] >= 0).sum() == 6  # both schools full


def test_unlimited_reach_fills_every_seat():
    """With no distance limit and enough seats, every pupil gets a school."""
    people = pupils_on_a_line(10)
    schools = pd.DataFrame({"x": [0.0, 9.0], "y": [0.0, 0.0], "capacity": [6, 6]})
    placed = assign_places(
        people, schools, PlaceSpec("school", ["child"]), np.random.default_rng(2)
    )
    assert (placed["school"].to_numpy()[:10] >= 0).all()
    assert placed.drop(columns="school").equals(people)


def test_locate_households_shares_one_point():
    """All members of a household stand at one point inside their region."""
    gpd = pytest.importorskip("geopandas")
    shapely = pytest.importorskip("shapely")
    from modelly import Model  # noqa: PLC0415
    from modelly.space.geo import GeoSpace  # noqa: PLC0415

    boxes = [shapely.box(0, 0, 100, 100), shapely.box(100, 0, 200, 100)]
    regions = gpd.GeoDataFrame({"name": ["r0", "r1"]}, geometry=boxes, crs=UTM)
    model = Model(rng=3)
    space = GeoSpace(regions.set_index("name"), random=model.random)
    people = pd.DataFrame(
        {"region": ["r0", "r0", "r0", "r1", "r1"], "household": [0, 0, 1, 2, 2]}
    )
    located = locate_households(people, space, model.rng)
    assert located.groupby("household")[["x", "y"]].nunique().eq(1).all().all()
    xy = located[["x", "y"]].to_numpy()
    assert space.regions_of(xy).tolist() == [0, 0, 0, 1, 1]  # region rows
