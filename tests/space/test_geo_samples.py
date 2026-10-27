"""The bundled Burlington samples load offline; the download script checks checksums."""

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("geopandas")
pytest.importorskip("rasterio")

from modelly.space.geo import samples

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "geo_data.py"
WORLDCOVER_NODATA = 0
LICENCES = ("ODbL 1.0", "CC BY 4.0", "public domain")


def _script():
    """Import scripts/geo_data.py as a module."""
    spec = importlib.util.spec_from_file_location("geo_data", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_roads_are_a_strongly_connected_street_graph():
    """255 junctions in UTM 18N, every edge with a positive length in metres."""
    import networkx as nx  # noqa: PLC0415

    from modelly import Model  # noqa: PLC0415

    roads = samples.sample_roads(random=Model(rng=1).random)
    assert len(roads.nodes) == 255
    assert roads.crs.to_epsg() == 32618
    assert nx.is_strongly_connected(roads.graph)
    lengths = [d["length"] for _, _, d in roads.graph.edges(data=True)]
    assert min(lengths) > 0


def test_landcover_is_a_worldcover_window():
    """120 x 120 pixels in WGS 84, every value a WorldCover class."""
    layer = samples.sample_landcover()
    assert layer.shape == (120, 120)
    assert layer.crs.to_epsg() == 4326
    values = set(np.unique(layer.values).tolist())
    assert values <= set(samples.WORLDCOVER_CLASSES)
    assert WORLDCOVER_NODATA not in values
    assert len(values) >= 5  # tree cover, grassland, cropland, built-up, water...


def test_neighbourhoods_are_the_county_tracts():
    """41 valid tract polygons of Chittenden County, indexed by GEOID."""
    tracts = samples.sample_neighbourhoods()
    assert len(tracts) == 41
    assert tracts.index.str.startswith("50007").all()
    assert tracts.is_valid.all()
    assert tracts.crs.to_epsg() == 4326


def test_notice_names_every_file_and_licence():
    """Each bundled file has its licence, source and checksum in NOTICE.md."""
    notice = samples.NOTICE.read_text(encoding="utf-8")
    for path in (samples.ROADS, samples.LANDCOVER, samples.TRACTS):
        assert path.is_file()
        assert path.name in notice
    for licence in LICENCES:
        assert licence in notice
    for source in _script().SOURCES:
        assert source.sha256 in notice


def test_script_checksums_files_and_osm_elements(tmp_path):
    """Files hash as bytes; an Overpass reply hashes by its sorted elements only."""
    geo_data = _script()
    plain = geo_data.Source("a.bin", "https://example.invalid/a.bin", "0" * 64)
    path = tmp_path / "a.bin"
    path.write_bytes(b"modelly")
    assert geo_data.sha256(plain, path) == hashlib.sha256(b"modelly").hexdigest()
    osm = geo_data.Source("o.json", "https://example.invalid/", "0" * 64, query="q")
    elements = [{"type": "way", "id": 2}, {"type": "node", "id": 1, "lat": 44.0}]
    first, second = tmp_path / "1.json", tmp_path / "2.json"
    first.write_text(json.dumps({"osm3s": {"t": "a"}, "elements": elements}))
    second.write_text(json.dumps({"osm3s": {"t": "b"}, "elements": elements[::-1]}))
    assert geo_data.sha256(osm, first) == geo_data.sha256(osm, second)
    assert not geo_data.verify(tmp_path)  # the real sources are not here
