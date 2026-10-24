"""GeoSpace: CRS handling, region lookup, neighbourhoods and export."""

import numpy as np
import pytest

gpd = pytest.importorskip("geopandas")
shapely = pytest.importorskip("shapely")
pytest.importorskip("pyproj")

from modelly import Model  # noqa: E402
from modelly.space.geo import GeoAgent, GeoSpace  # noqa: E402
from tests.space.conftest import UTM  # noqa: E402

WGS84 = "EPSG:4326"
ZONE_CENTRE = (500_000.0, 5_000_000.0)  # metres: well inside UTM zone 31N


def make_space(regions, n=0, seed=1):
    """A model with a GeoSpace over ``regions`` and agents at region centres."""
    model = Model(rng=seed)
    space = GeoSpace(regions, random=model.random)
    centroids = regions.geometry.centroid
    for point in list(centroids)[:n]:
        GeoAgent(space, model, point)
    return model, space


def test_crs_from_regions_and_reprojection(city_regions):
    """The space adopts a projected CRS; geographic inputs are moved to UTM."""
    _, space = make_space(city_regions)
    assert space.crs.to_epsg() == 32631
    central = city_regions.set_geometry(city_regions.translate(*ZONE_CENTRE))
    lonlat = central.to_crs(WGS84)
    projected = GeoSpace(lonlat, random=Model(rng=1).random)
    assert projected.crs.is_projected
    assert projected.crs.to_epsg() == 32631
    np.testing.assert_allclose(
        projected.regions.total_bounds, central.total_bounds, atol=1e-3
    )


def test_explicit_crs_reprojects_points(city_regions):
    """Points given in another CRS land where they belong in the space."""
    model, space = make_space(city_regions)
    target = shapely.Point(150, 250)
    lonlat = gpd.GeoSeries([target], crs=UTM).to_crs(WGS84).iloc[0]
    agent = GeoAgent(space, model, lonlat, crs=WGS84)
    np.testing.assert_allclose(agent.position, (150, 250), atol=1e-6)
    assert agent.region == "r7"
    agent.move_to((50, 50))
    assert agent.region == "r0"
    assert space.region_of((1000, 1000)) is None


def test_bounds_without_regions_and_errors():
    """A space without regions needs bounds; moving outside them is an error."""
    model = Model(rng=1)
    space = GeoSpace(random=model.random, bounds=(0, 0, 10, 10))
    agent = GeoAgent(space, model, (5, 5))
    with pytest.raises(ValueError):
        agent.move_to((20, 5))
    with pytest.raises(ValueError):
        GeoSpace(random=model.random)
    assert space.region_counts().empty


def test_region_membership_and_counts(city_regions):
    """Agents are counted per region and listed by region."""
    _, space = make_space(city_regions, n=9)
    assert space.region_counts().tolist() == [1] * 9
    assert [a.region for a in space.agents_in_region("r4")] == ["r4"]
    assert space.regions_of(np.array([[100.0, 50.0]])).tolist() == [0]  # border: first


def test_agents_within_geometry_and_distance(city_regions):
    """Inside a polygon, within a distance of a point or a geometry."""
    _, space = make_space(city_regions, n=9)
    assert len(space.agents_within(shapely.box(0, 0, 200, 200))) == 4
    assert len(space.agents_within((150, 150), distance=100.0)) == 5
    line = shapely.LineString([(0, 150), (300, 150)])
    assert len(space.agents_within(line, distance=1.0)) == 3
    radius_agents, _ = space.get_agents_in_radius((150, 150), radius=100.0)
    assert len(radius_agents) == 5


def test_contiguity_queen_and_rook(city_regions):
    """The centre block touches eight regions at a point and four along a side."""
    _, space = make_space(city_regions)
    assert len(space.region_neighbors("r4")) == 8
    assert space.region_neighbors("r4", kind="rook") == ["r1", "r3", "r5", "r7"]
    assert space.region_neighbors("r0", kind="rook") == ["r1", "r3"]
    queen = space.contiguity("queen")
    assert (queen != queen.T).nnz == 0
    assert space.region_neighbors("r0", distance=1.0) == ["r1", "r3", "r4"]
    assert space.regions_within(shapely.Point(150, 150), distance=60) == [
        "r1",
        "r3",
        "r4",
        "r5",
        "r7",
    ]
    with pytest.raises(ValueError):
        space.contiguity("bishop")


def test_random_points_fall_in_region(city_regions):
    """Points drawn for a region are inside it, and reproducible from the seed."""
    model, space = make_space(city_regions)
    points = space.random_points("r5", 20, model.rng)
    assert points.shape == (20, 2)
    assert (space.regions_of(points) == 5).all()
    again = make_space(city_regions)[1].random_points("r5", 20, Model(rng=1).rng)
    np.testing.assert_array_equal(points, again)


def test_export_geojson_and_geoparquet(city_regions, tmp_path):
    """Agents and regions round-trip through GeoParquet and GeoJSON."""
    pytest.importorskip("pyarrow")
    _, space = make_space(city_regions, n=3)
    agents = space.to_geodataframe(attributes=("unique_id",))
    assert list(agents["region"]) == ["r0", "r1", "r2"]
    space.to_file(tmp_path / "agents.parquet")
    back = gpd.read_parquet(tmp_path / "agents.parquet")
    assert back.crs == agents.crs and back.geometry.equals(agents.geometry)
    path = space.to_file(tmp_path / "regions.geojson", what="regions")
    text = path.read_text(encoding="utf-8")
    assert '"n_agents": 1' in text and "FeatureCollection" in text
    with pytest.raises(ValueError):
        space.to_file(tmp_path / "agents.shp")
    with pytest.raises(ValueError):
        space.to_geodataframe("roads")


def test_project_geometry_and_frames(city_regions):
    """Shapely geometries and GeoPandas objects are brought into the space's CRS."""
    _, space = make_space(city_regions)
    lonlat = city_regions.to_crs(WGS84)
    assert space.project(lonlat).crs == space.crs
    polygon = space.project(lonlat.geometry.iloc[4], crs=WGS84)
    assert polygon.centroid.distance(shapely.Point(150, 150)) < 1e-3
    assert space.project(polygon) is polygon
