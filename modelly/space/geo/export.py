"""GeoDataFrames of a ``GeoSpace`` and writing them as GeoParquet or GeoJSON."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd
import shapely

from modelly.space.geo.regions import NO_REGION

if TYPE_CHECKING:
    from modelly.space.geo.space import GeoSpace

PARQUET_SUFFIXES = (".parquet", ".geoparquet")
GEOJSON_SUFFIXES = (".geojson", ".json")


def agents_frame(space: GeoSpace, attributes: Sequence[str] = ()) -> gpd.GeoDataFrame:
    """One row per agent: ``unique_id``, ``region``, the named attributes and a point."""
    agents = space.active_agents
    rows = space.agent_regions()
    labels = list(space.regions.index)
    data = {
        "unique_id": [agent.unique_id for agent in agents],
        "region": [None if r == NO_REGION else labels[r] for r in rows],
    }
    for name in attributes:
        data[name] = [getattr(agent, name) for agent in agents]
    positions = space.agent_positions
    geometry = shapely.points(positions[:, 0], positions[:, 1])
    return gpd.GeoDataFrame(data, geometry=geometry, crs=space.crs)


def regions_frame(space: GeoSpace) -> gpd.GeoDataFrame:
    """The regions with an ``n_agents`` column counting the agents in each."""
    frame = space.regions.copy()
    frame["n_agents"] = space.region_counts().to_numpy()
    return frame


def write_frame(frame: gpd.GeoDataFrame, path: Path) -> Path:
    """Write ``frame`` to ``path``: GeoParquet or GeoJSON, chosen by the suffix."""
    suffix = path.suffix.lower()
    if suffix in PARQUET_SUFFIXES:
        frame.to_parquet(path)
    elif suffix in GEOJSON_SUFFIXES:
        text = frame.to_json(to_wgs84=frame.crs is not None)
        path.write_text(text, encoding="utf-8", newline="\n")
    else:
        raise ValueError(
            f"Unknown suffix {path.suffix!r}: use one of "
            f"{PARQUET_SUFFIXES + GEOJSON_SUFFIXES}."
        )
    return path
