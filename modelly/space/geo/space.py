"""A vector geospatial space: agents as points, polygons as regions, one CRS.

``GeoSpace`` is a ``ContinuousSpace`` whose coordinates are those of a projected
coordinate reference system (metres for UTM), so the continuous space's KD-tree
queries (``get_agents_in_radius``, ``neighbors_within``, ``get_k_nearest_agents``)
measure real distances. Agent positions stay one numpy array; regions are the rows
of a GeoDataFrame, indexed by an STRtree for point-in-polygon and distance lookups.

The CRS is set once, at the space. Inputs that carry another CRS (regions, points,
geometries) are reprojected into it; a geographic CRS (latitude and longitude) is
replaced by the UTM zone that covers the regions, since degrees are not distances.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from random import Random
from typing import TYPE_CHECKING, Any

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
import shapely

from modelly.space.continuous.space import ContinuousSpace
from modelly.space.geo import export
from modelly.space.geo.regions import NO_REGION, RegionQueriesMixin

if TYPE_CHECKING:
    from modelly.core.agent import Agent

# Candidate points drawn per accepted point and the cap on rejection rounds in random_points.
_OVERSAMPLE = 4
_MAX_ROUNDS = 1000


class GeoSpace(RegionQueriesMixin, ContinuousSpace):
    """Agents as points and polygons as regions, in one projected CRS.

    Attributes:
        crs: the space's ``pyproj.CRS``, or ``None`` for plain planar coordinates.
        regions: a GeoDataFrame of the region polygons in ``crs``; its index labels the regions.
    """

    def __init__(
        self,
        regions: gpd.GeoDataFrame | None = None,
        crs: Any = None,
        random: Random | None = None,
        *,
        bounds: Sequence[float] | None = None,
        n_agents: int = 100,
    ) -> None:
        """Create a geospatial space.

        Args:
            regions: polygons that make up the study area, in any CRS; reprojected to ``crs``.
            crs: the space's CRS (anything ``pyproj.CRS`` accepts). Defaults to the CRS of
                ``regions``, or to its UTM zone when that CRS is geographic.
            random: a seeded ``random.Random``, usually ``model.random``.
            bounds: ``(minx, miny, maxx, maxy)`` in ``crs``; defaults to the regions' bounds.
            n_agents: the expected number of agents, to size the position array.
        """
        self.crs = _resolve_crs(regions, crs)
        self.regions = _prepare_regions(regions, self.crs)
        if bounds is None:
            if self.regions.empty:
                raise ValueError("GeoSpace needs regions or explicit bounds.")
            bounds = self.regions.total_bounds
        minx, miny, maxx, maxy = (float(b) for b in bounds)
        super().__init__([[minx, maxx], [miny, maxy]], random=random, n_agents=n_agents)
        self._reset_caches()

    def _reset_caches(self) -> None:
        """Forget the spatial indices; they are rebuilt on first use."""
        self._region_tree_cache = None
        self._contiguity_cache: dict[str, Any] = {}
        self._agent_regions_cache: tuple[int, np.ndarray] | None = None
        self._neighbors_cache = None

    def __getstate__(self) -> dict:
        """Drop the STRtree and the caches; a loaded space rebuilds them when queried."""
        state = super().__getstate__()
        for name in (
            "_region_tree_cache",
            "_contiguity_cache",
            "_agent_regions_cache",
        ):
            state.pop(name, None)
        return state

    def __setstate__(self, state: dict) -> None:
        """Restore the position view and start with empty spatial indices."""
        super().__setstate__(state)
        self._reset_caches()

    def project(self, geometry: Any, crs: Any = None) -> Any:
        """Return ``geometry`` in the space's CRS.

        Args:
            geometry: a Shapely geometry, a GeoSeries or a GeoDataFrame.
            crs: the CRS ``geometry`` is in; GeoPandas objects default to their own CRS.
                ``None`` for a Shapely geometry means it is already in the space's CRS.
        """
        if isinstance(geometry, gpd.GeoSeries | gpd.GeoDataFrame):
            if geometry.crs is None or self.crs is None:
                return geometry if crs is None else geometry.set_crs(crs)
            return geometry.to_crs(self.crs)
        if crs is None or self.crs is None:
            return geometry
        transformer = pyproj.Transformer.from_crs(crs, self.crs, always_xy=True)
        return shapely.transform(
            geometry, lambda xy: np.column_stack(transformer.transform(*xy.T))
        )

    def project_points(self, xy: np.ndarray, crs: Any = None) -> np.ndarray:
        """Return an ``(n, 2)`` array of coordinates in ``crs`` reprojected to the space's CRS."""
        xy = np.atleast_2d(np.asarray(xy, dtype=float))
        if crs is None or self.crs is None:
            return xy
        transformer = pyproj.Transformer.from_crs(crs, self.crs, always_xy=True)
        return np.column_stack(transformer.transform(xy[:, 0], xy[:, 1]))

    def _as_xy(self, point: Any, crs: Any = None) -> np.ndarray:
        """A point (Shapely ``Point`` or ``(x, y)``) as a length-2 array in the space's CRS."""
        if isinstance(point, shapely.Point):
            point = (point.x, point.y)
        return self.project_points(point, crs)[0]

    def move_to(self, agent: Agent, point: Any, crs: Any = None) -> None:
        """Move ``agent`` to ``point`` (a Shapely ``Point`` or ``(x, y)``, in ``crs``)."""
        agent.position = self._as_xy(point, crs)

    def region_of(self, point: Any, crs: Any = None) -> Any:
        """Return the label of the region containing ``point``, or ``None`` outside all regions."""
        row = int(self.regions_of(self._as_xy(point, crs)[np.newaxis, :])[0])
        return None if row == NO_REGION else self.regions.index[row]

    def regions_of(self, xy: np.ndarray) -> np.ndarray:
        """Region row (position in ``regions``) of every point in ``xy``; ``-1`` outside.

        A point on a shared border belongs to the region listed first.
        """
        xy = np.atleast_2d(np.asarray(xy, dtype=float))
        out = np.full(xy.shape[0], len(self.regions), dtype=np.intp)
        if xy.shape[0] and len(self.regions):
            points, rows = self._region_tree.query(
                shapely.points(xy), predicate="intersects"
            )
            np.minimum.at(out, points, rows)
        out[out == len(self.regions)] = NO_REGION
        return out

    def agent_regions(self) -> np.ndarray:
        """Region row of every agent, in ``active_agents`` order; cached until an agent moves."""
        positions = self.agent_positions
        key = hash((positions.shape, positions.tobytes()))
        cached = self._agent_regions_cache
        if cached is None or cached[0] != key:
            cached = (key, self.regions_of(positions))
            self._agent_regions_cache = cached
        return cached[1]

    def agents_in_region(self, label: Any) -> list[Agent]:
        """The agents whose position lies in the region labelled ``label``."""
        row = self.regions.index.get_loc(label)
        hits = np.flatnonzero(self.agent_regions() == row)
        return [self.active_agents[i] for i in hits]

    def region_counts(self) -> pd.Series:
        """Number of agents in every region, indexed by region label."""
        rows = self.agent_regions()
        counts = np.bincount(rows[rows != NO_REGION], minlength=len(self.regions))
        return pd.Series(counts, index=self.regions.index, name="n_agents")

    def agents_within(
        self, target: Any, distance: float | None = None, crs: Any = None
    ) -> list[Agent]:
        """The agents inside ``target``, or within ``distance`` of it.

        Args:
            target: a Shapely geometry or an ``(x, y)`` point.
            distance: in the space's units; ``None`` means inside (or on) ``target`` itself.
            crs: the CRS of ``target``, if not the space's.
        """
        if not isinstance(target, shapely.Geometry):
            target = shapely.Point(self._as_xy(target, crs))
        else:
            target = self.project(target, crs)
        x, y = self.agent_positions[:, 0], self.agent_positions[:, 1]
        if distance is None:
            mask = shapely.intersects_xy(target, x, y)
        else:
            mask = shapely.dwithin(target, shapely.points(x, y), distance)
        return [self.active_agents[i] for i in np.flatnonzero(mask)]

    def random_points(self, label: Any, n: int, rng: np.random.Generator) -> np.ndarray:
        """``n`` points drawn uniformly inside region ``label``, as an ``(n, 2)`` array.

        Args:
            label: the region label.
            n: the number of points.
            rng: a numpy generator, usually ``model.rng``.
        """
        polygon = self.regions.geometry.loc[label]
        minx, miny, maxx, maxy = polygon.bounds
        accepted: list[np.ndarray] = []
        found = 0
        for _ in range(_MAX_ROUNDS):
            if found >= n:
                break
            size = max(n - found, 1) * _OVERSAMPLE
            xy = rng.uniform((minx, miny), (maxx, maxy), size=(size, 2))
            inside = xy[shapely.contains_xy(polygon, xy[:, 0], xy[:, 1])]
            accepted.append(inside)
            found += inside.shape[0]
        if found < n:
            raise ValueError(f"Could not place {n} points inside region {label!r}.")
        return np.concatenate(accepted)[:n]

    def to_geodataframe(
        self, what: str = "agents", attributes: Sequence[str] = ()
    ) -> gpd.GeoDataFrame:
        """The agents (as points, with ``attributes``) or the regions (with agent counts)."""
        if what == "agents":
            return export.agents_frame(self, attributes)
        if what == "regions":
            return export.regions_frame(self)
        raise ValueError(f"what must be 'agents' or 'regions', not {what!r}.")

    def to_file(
        self, path: str | Path, what: str = "agents", attributes: Sequence[str] = ()
    ) -> Path:
        """Write ``to_geodataframe(what, attributes)`` as GeoParquet or GeoJSON, by suffix.

        ``.parquet`` and ``.geoparquet`` write GeoParquet (needs ``pyarrow``); ``.geojson``
        and ``.json`` write GeoJSON in WGS 84, as the GeoJSON standard asks.
        """
        return export.write_frame(self.to_geodataframe(what, attributes), Path(path))


def _resolve_crs(regions: gpd.GeoDataFrame | None, crs: Any) -> pyproj.CRS | None:
    """The space's CRS: the one asked for, else the regions', projected if geographic."""
    if crs is not None:
        return pyproj.CRS.from_user_input(crs)
    if regions is None or regions.crs is None:
        return None
    if regions.crs.is_geographic:
        return regions.estimate_utm_crs()
    return regions.crs


def _prepare_regions(
    regions: gpd.GeoDataFrame | None, crs: pyproj.CRS | None
) -> gpd.GeoDataFrame:
    """The regions reprojected to ``crs``; an empty frame when there are none."""
    if regions is None:
        return gpd.GeoDataFrame(geometry=gpd.GeoSeries([], crs=crs), crs=crs)
    if regions.crs is None or crs is None:
        return regions.set_crs(crs, allow_override=True) if crs else regions.copy()
    return regions.to_crs(crs)
