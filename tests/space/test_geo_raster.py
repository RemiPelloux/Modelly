"""RasterLayer: alignment with a grid, sampling, GeoTIFF round trip and reprojection."""

import numpy as np
import pytest

pytest.importorskip("geopandas")
rasterio = pytest.importorskip("rasterio")

from modelly import Model  # noqa: E402
from modelly.space.geo import GeoAgent, GeoSpace, RasterLayer  # noqa: E402
from tests.space.conftest import UTM  # noqa: E402

PIXEL = 100.0
NODATA = -1.0


def tiny_raster():
    """Three rows by four columns, north-up, 100 m pixels, the north-west corner at y=300."""
    band = np.arange(12.0).reshape(3, 4)
    band[0, 3] = NODATA
    transform = rasterio.transform.from_origin(0.0, 300.0, PIXEL, PIXEL)
    return RasterLayer(band, transform, crs=UTM, nodata=NODATA)


def test_values_are_grid_oriented():
    """``values[x, y]`` has ``y`` northward; ``array`` is the north-up band."""
    raster = tiny_raster()
    assert raster.shape == (4, 3)
    assert raster.values[0, 0] == 8.0  # south-west pixel
    assert raster.values[0, 2] == 0.0  # north-west pixel
    np.testing.assert_array_equal(raster.array[1], [4.0, 5.0, 6.0, 7.0])
    with pytest.raises(ValueError):
        RasterLayer(np.zeros(3), raster.transform)


def test_sampling_points_and_agents(city_regions):
    """Samples follow the transform; outside and nodata give nan."""
    raster = tiny_raster()
    values = raster.sample(np.array([[50, 50], [350, 250], [150, 250], [500, 50]]))
    np.testing.assert_array_equal(values[:1], [8.0])
    assert np.isnan(values[1]) and np.isnan(values[3])
    assert values[2] == 1.0
    model = Model(rng=1)
    space = GeoSpace(city_regions, random=model.random)
    GeoAgent(space, model, (250, 150))
    np.testing.assert_array_equal(raster.sample_agents(space), [6.0])
    np.testing.assert_allclose(raster.cell_centers()[0, 0], (50.0, 50.0))
    assert raster.cells_of(np.array([[50.0, 50.0]])).tolist() == [[0, 0]]


def test_attached_layer_is_shared_with_grid():
    """Writes through ``cell.<name>`` reach the raster, and the other way round."""
    raster = tiny_raster()
    model = Model(rng=1)
    grid = raster.to_grid("land", random=model.random)
    assert grid.dimensions == (4, 3)
    assert grid[(0, 0)].land == 8.0
    grid[(1, 2)].land = 42.0
    assert raster.array[0, 1] == 42.0
    raster.values[3, 0] = 7.5
    assert grid[(3, 0)].land == 7.5


def test_geotiff_round_trip(tmp_path):
    """Writing back to GeoTIFF keeps values, transform, CRS and nodata."""
    raster = tiny_raster()
    raster.values[2, 1] = 99.0
    path = raster.to_file(tmp_path / "land.tif")
    back = RasterLayer.from_file(path)
    np.testing.assert_array_equal(back.values, raster.values)
    assert back.transform == raster.transform
    assert back.crs == raster.crs
    assert back.nodata == NODATA


def test_reproject_and_sample_across_crs():
    """A raster warped to another CRS samples the same values at the same places."""
    raster = tiny_raster()
    centre = np.array([[150.0, 150.0]])
    warped = raster.reproject("EPSG:3857")
    assert warped.crs.to_epsg() == 3857
    assert warped.sample(centre, crs=UTM)[0] == raster.sample(centre)[0]
    with pytest.raises(ValueError):
        RasterLayer(np.zeros((2, 2)), raster.transform).reproject(UTM)
