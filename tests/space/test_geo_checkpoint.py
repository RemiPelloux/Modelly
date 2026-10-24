"""Checkpoints of geospatial models: positions, regions, rasters and roads survive."""

import numpy as np
import pytest

pytest.importorskip("geopandas")
rasterio = pytest.importorskip("rasterio")

from modelly import Model  # noqa: E402
from modelly.space.geo import GeoAgent, GeoSpace, RasterLayer, RoadNetwork  # noqa: E402
from tests.space.conftest import UTM  # noqa: E402


def roundtrip(model, tmp_path):
    """Save ``model`` and load it back."""
    model.save(tmp_path / "geo.ckpt")
    return Model.load(tmp_path / "geo.ckpt")


def test_geospace_survives_and_rebuilds_indices(city_regions, tmp_path):
    """Agents keep positions and regions; the STRtree and caches are rebuilt."""
    model = Model(rng=1)
    model.space = GeoSpace(city_regions, random=model.random)
    for point in city_regions.geometry.centroid:
        GeoAgent(model.space, model, point)
    model.space.contiguity("rook")
    model.space.region_counts()
    restored = roundtrip(model, tmp_path)
    space = restored.space
    assert space._region_tree_cache is None and space._contiguity_cache == {}
    assert space.crs == model.space.crs
    assert space.region_counts().tolist() == [1] * 9
    assert space.region_neighbors("r4", kind="rook") == ["r1", "r3", "r5", "r7"]
    agent = next(iter(space.agents))
    agent.move_to((250.0, 250.0))
    assert space.agent_positions[agent._modelly_index].tolist() == [250.0, 250.0]
    assert agent.region == "r8"
    assert len(space.neighbors_within(150.0)) == 9


def test_raster_layer_stays_shared_with_grid(tmp_path):
    """After a load the grid layer and the raster are still one array."""
    model = Model(rng=2)
    transform = rasterio.transform.from_origin(0.0, 200.0, 100.0, 100.0)
    model.raster = RasterLayer(np.arange(4.0).reshape(2, 2), transform, crs=UTM)
    model.grid = model.raster.to_grid("land", random=model.random)
    restored = roundtrip(model, tmp_path)
    restored.grid[(0, 0)].land = 9.0
    assert restored.raster.array[1, 0] == 9.0
    assert restored.raster.values is restored.grid.land
    assert restored.raster.transform == transform


def test_road_network_routes_after_load(grid_roads, tmp_path):
    """Routing matrices are dropped by the save and rebuilt on use."""
    model = Model(rng=3)
    model.roads = RoadNetwork(grid_roads, random=model.random)
    model.roads.add_travel_times(10.0)
    expected = model.roads.distance_matrix([(0, 0)])
    restored = roundtrip(model, tmp_path)
    assert restored.roads._csr_cache == {}
    np.testing.assert_array_equal(restored.roads.distance_matrix([(0, 0)]), expected)
    assert restored.roads.travel_time((0, 0), (2, 2)) == 40.0
    assert restored.roads.node_of((240.0, 260.0)) == (2, 2)
