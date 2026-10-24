"""Rasters as property layers: a GeoTIFF band aligned to a grid space.

A ``RasterLayer`` keeps one band in ``values``, shaped like an orthogonal grid
(``(width, height)``, indexed ``[x, y]`` with ``y = 0`` the southern row), so it can be
attached to a grid as a property layer: ``cell.<name>`` and the raster share one array,
and a vectorised update of the layer is a raster update. The affine ``transform`` maps
pixel ``(column, row)`` of the north-up band to map coordinates in ``crs``, as in rasterio.
"""

from __future__ import annotations

from pathlib import Path
from random import Random
from typing import TYPE_CHECKING, Any

import numpy as np
import pyproj

from modelly.space.geo._deps import require

if TYPE_CHECKING:
    from modelly.space.geo.space import GeoSpace
    from modelly.space.grid.base import Grid

# Pixel offset of a cell's centre from its upper-left corner, and the GeoTIFF band written.
_CENTER = 0.5
_BAND = 1
_BAND_NDIM = 2
OUTSIDE = -1


class RasterLayer:
    """One raster band with its transform, CRS and nodata value.

    Attributes:
        values: the band, shape ``(width, height)``, indexed ``[x, y]`` with ``y`` northward.
        transform: the ``affine.Affine`` from pixel ``(column, row)`` to map coordinates.
        crs: the ``pyproj.CRS`` of the map coordinates, or ``None``.
        nodata: the value marking missing cells, or ``None``.
    """

    def __init__(
        self, data: np.ndarray, transform: Any, crs: Any = None, nodata: Any = None
    ) -> None:
        """Wrap a north-up band (rows from north to south, as rasterio reads it).

        Args:
            data: a 2-D array, shape ``(rows, columns)``.
            transform: an ``affine.Affine``, or its six coefficients ``(a, b, c, d, e, f)``.
            crs: anything ``pyproj.CRS`` accepts.
            nodata: the value of missing cells.
        """
        data = np.asarray(data)
        if data.ndim != _BAND_NDIM:
            raise ValueError(f"A raster band is 2-D, got shape {data.shape}.")
        affine = require("affine", "geo")
        self.values = np.ascontiguousarray(np.flipud(data).T)
        self.transform = affine.Affine(*tuple(transform)[:6])
        self.crs = None if crs is None else pyproj.CRS.from_user_input(crs)
        self.nodata = nodata

    @property
    def shape(self) -> tuple[int, int]:
        """``(width, height)``: the dimensions of a grid aligned to the raster."""
        return self.values.shape

    @property
    def array(self) -> np.ndarray:
        """The band north-up, shape ``(rows, columns)``: a view of ``values``."""
        return np.flipud(self.values.T)

    @classmethod
    def from_file(cls, path: str | Path, band: int = _BAND) -> RasterLayer:
        """Read one band of a raster file (GeoTIFF or any format rasterio reads)."""
        rasterio = require("rasterio", "geo")
        with rasterio.open(Path(path)) as source:
            return cls(
                source.read(band),
                source.transform,
                crs=source.crs.to_wkt() if source.crs else None,
                nodata=source.nodata,
            )

    def to_file(self, path: str | Path) -> Path:
        """Write the band, with its transform, CRS and nodata value, as a GeoTIFF."""
        rasterio = require("rasterio", "geo")
        path = Path(path)
        band = self.array
        profile = {
            "driver": "GTiff",
            "height": band.shape[0],
            "width": band.shape[1],
            "count": 1,
            "dtype": band.dtype.name,
            "transform": self.transform,
            "crs": self.crs.to_wkt() if self.crs else None,
            "nodata": self.nodata,
        }
        with rasterio.open(path, "w", **profile) as target:
            target.write(band, _BAND)
        return path

    def cells_of(self, xy: np.ndarray, crs: Any = None) -> np.ndarray:
        """Grid coordinate ``(x, y)`` of the cell under every point, ``-1`` outside.

        Args:
            xy: an ``(n, 2)`` array of map coordinates.
            crs: the CRS of ``xy`` when it differs from the raster's.
        """
        xy = self._to_raster_crs(np.atleast_2d(np.asarray(xy, dtype=float)), crs)
        inverse = ~self.transform
        cols = np.floor(inverse.a * xy[:, 0] + inverse.b * xy[:, 1] + inverse.c)
        rows = np.floor(inverse.d * xy[:, 0] + inverse.e * xy[:, 1] + inverse.f)
        width, height = self.shape
        cells = np.column_stack((cols, height - 1 - rows)).astype(np.intp)
        outside = (cols < 0) | (cols >= width) | (rows < 0) | (rows >= height)
        cells[outside] = OUTSIDE
        return cells

    def sample(self, xy: np.ndarray, crs: Any = None) -> np.ndarray:
        """The raster value under every point, as floats; ``nan`` outside or on nodata."""
        cells = self.cells_of(xy, crs)
        inside = cells[:, 0] != OUTSIDE
        out = np.full(cells.shape[0], np.nan)
        out[inside] = self.values[cells[inside, 0], cells[inside, 1]]
        if self.nodata is not None:
            out[out == self.nodata] = np.nan
        return out

    def sample_agents(self, space: GeoSpace) -> np.ndarray:
        """The raster value at every agent of ``space``, in ``active_agents`` order."""
        return self.sample(space.agent_positions, crs=space.crs)

    def cell_centers(self) -> np.ndarray:
        """Map coordinates of every cell centre, shape ``(width, height, 2)``."""
        width, height = self.shape
        x, y = np.meshgrid(np.arange(width), np.arange(height), indexing="ij")
        cols, rows = x + _CENTER, (height - 1 - y) + _CENTER
        t = self.transform
        return np.stack(
            (t.a * cols + t.b * rows + t.c, t.d * cols + t.e * rows + t.f), -1
        )

    def attach(self, grid: Grid, name: str, read_only: bool = False) -> None:
        """Attach ``values`` to ``grid`` as property layer ``name`` (shared, not copied)."""
        grid.add_property_layer(name, self.values, read_only=read_only)

    def to_grid(self, name: str, random: Random | None = None, **kwargs) -> Grid:
        """A new ``OrthogonalMooreGrid`` of the raster's shape with the band as layer ``name``.

        Extra keyword arguments (``torus``, ``capacity``, ...) go to the grid.
        """
        from modelly.space.grid.grids import OrthogonalMooreGrid  # noqa: PLC0415

        grid = OrthogonalMooreGrid(self.shape, random=random, **kwargs)
        self.attach(grid, name)
        return grid

    def reproject(self, crs: Any, resampling: str = "nearest") -> RasterLayer:
        """A new layer warped to ``crs`` with rasterio (``resampling`` names the method)."""
        warp = require("rasterio.warp", "geo")
        if self.crs is None:
            raise ValueError("Cannot reproject a raster that has no CRS.")
        dst_crs = pyproj.CRS.from_user_input(crs)
        rows, cols = self.array.shape
        bounds = _bounds(self.transform, cols, rows)
        transform, width, height = warp.calculate_default_transform(
            self.crs.to_wkt(), dst_crs.to_wkt(), cols, rows, *bounds
        )
        fill = np.nan if self.nodata is None else self.nodata
        target = np.full((height, width), fill, dtype=np.result_type(self.values, fill))
        warp.reproject(
            source=self.array,
            destination=target,
            src_transform=self.transform,
            src_crs=self.crs.to_wkt(),
            dst_transform=transform,
            dst_crs=dst_crs.to_wkt(),
            resampling=getattr(warp.Resampling, resampling),
            src_nodata=self.nodata,
            dst_nodata=fill,
        )
        return RasterLayer(target, transform, crs=dst_crs, nodata=self.nodata)

    def _to_raster_crs(self, xy: np.ndarray, crs: Any) -> np.ndarray:
        """Reproject ``xy`` from ``crs`` to the raster's CRS when they differ."""
        if crs is None or self.crs is None:
            return xy
        source = pyproj.CRS.from_user_input(crs)
        if source == self.crs:
            return xy
        transformer = pyproj.Transformer.from_crs(source, self.crs, always_xy=True)
        return np.column_stack(transformer.transform(xy[:, 0], xy[:, 1]))


def _bounds(transform: Any, cols: int, rows: int) -> tuple[float, float, float, float]:
    """``(left, bottom, right, top)`` of a north-up raster with this transform."""
    xs = [transform.c, transform.c + transform.a * cols]
    ys = [transform.f, transform.f + transform.e * rows]
    return min(xs), min(ys), max(xs), max(ys)
