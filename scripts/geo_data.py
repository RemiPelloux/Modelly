#!/usr/bin/env python3
"""Download the full geospatial sources of the bundled samples, check them, rebuild the samples.

The zoo's real-data models (``road_traffic``, ``habitat_selection``,
``schelling_regions``) run on three small extracts of Burlington, Vermont, bundled in
``modelly/space/geo/data`` with their licences in ``NOTICE.md`` there. This script fetches
the full sources they were cut from, checks every download against its SHA-256, and cuts
the extracts again::

    python scripts/geo_data.py download DIR    fetch the sources into DIR and verify them
    python scripts/geo_data.py verify DIR      verify sources already in DIR
    python scripts/geo_data.py build DIR       rebuild the bundled samples from DIR

``download`` and ``verify`` need only the standard library; ``build`` needs the ``geo``
extra. The OpenStreetMap extract is an Overpass query pinned to a date, so the elements
never change, but the server adds its own timestamp to the reply: its checksum is over
the elements, sorted by type and id and written as compact JSON with sorted keys.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "modelly" / "space" / "geo" / "data"
USER_AGENT = "modelly-geo-data/1.0"
CHUNK = 1 << 20
RETRIES = 4
BACKOFF = 30.0  # seconds before the second try; doubled after every failure
TIMEOUT = 300.0
EXIT_OK, EXIT_BAD = 0, 1

OVERPASS = "https://overpass-api.de/api/interpreter"
OSM_DATE = "2026-10-01T00:00:00Z"
OSM_BBOX = (44.4700, -73.2200, 44.4840, -73.2000)  # south, west, north, east
OSM_HIGHWAYS = (
    "primary|secondary|tertiary|unclassified|residential|living_street"
    "|primary_link|secondary_link|tertiary_link"
)
OSM_QUERY = (
    f'[out:json][timeout:90][date:"{OSM_DATE}"];'
    f'way["highway"~"^({OSM_HIGHWAYS})$"]({",".join(map(str, OSM_BBOX))});'
    "(._;>;);out body qt;"
)


@dataclass(frozen=True)
class Source:
    """One full source: where it comes from, its file name and its SHA-256."""

    name: str
    url: str
    sha256: str
    query: str | None = None


SOURCES = (
    Source(
        "cb_2023_50_tract_500k.zip",
        "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_50_tract_500k.zip",
        "049cfa9b968db3de27c15fa0dc2f52fcb96ad87c02881e7c66dc52644bade202",
    ),
    Source(
        "ESA_WorldCover_10m_2021_v200_N42W075_Map.tif",
        "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
        "ESA_WorldCover_10m_2021_v200_N42W075_Map.tif",
        "6bc1b5a5e5c6a680cf4b3c19ef069f4dc817042fdb952862cefb128df5a322d6",
    ),
    Source(
        "burlington_osm.json",
        OVERPASS,
        "b4b86ccc29b9490e5ea00cd584582c412ccaf2a3abd2fedaf88fc392ce329c14",
        OSM_QUERY,
    ),
)


def sha256(source: Source, path: Path) -> str:
    """The checksum of a downloaded source (of its sorted elements for OpenStreetMap)."""
    if source.query is None:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(CHUNK), b""):
                digest.update(block)
        return digest.hexdigest()
    elements = json.loads(path.read_text(encoding="utf-8"))["elements"]
    ordered = sorted(elements, key=lambda e: (e["type"], e["id"]))
    text = json.dumps(ordered, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fetch(source: Source, path: Path) -> None:
    """Download ``source`` to ``path``, retrying a busy server with a growing wait."""
    data = None
    if source.query is not None:
        data = urllib.parse.urlencode({"data": source.query}).encode("ascii")
    request = urllib.request.Request(
        source.url, data=data, headers={"User-Agent": USER_AGENT}
    )
    wait = BACKOFF
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as reply:
                path.write_bytes(reply.read())
            return
        except OSError as error:
            if attempt == RETRIES - 1:
                raise
            sys.stderr.write(f"{source.name}: {error}; retrying in {wait:.0f} s\n")
            time.sleep(wait)
            wait *= 2


def verify(directory: Path) -> bool:
    """Check every source in ``directory`` against its SHA-256; report each one."""
    good = True
    for source in SOURCES:
        path = directory / source.name
        found = sha256(source, path) if path.is_file() else "missing"
        ok = found == source.sha256
        good &= ok
        sys.stdout.write(f"{'ok ' if ok else 'BAD'} {source.name} {found}\n")
    return good


def download(directory: Path) -> bool:
    """Fetch the sources not yet in ``directory``, then verify them all."""
    directory.mkdir(parents=True, exist_ok=True)
    for source in SOURCES:
        path = directory / source.name
        if not path.is_file():
            fetch(source, path)
    return verify(directory)


def build(directory: Path) -> bool:
    """Cut the bundled samples from verified sources in ``directory``."""
    if not verify(directory):
        return False
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import geo_data_build  # noqa: PLC0415 - needs the geo extra, only for build

    geo_data_build.build_all(directory, DATA)
    return True


def main(argv: list[str] | None = None) -> int:
    """Run the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("download", "verify", "build"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    action = {"download": download, "verify": verify, "build": build}[args.command]
    return EXIT_OK if action(args.directory) else EXIT_BAD


if __name__ == "__main__":
    sys.exit(main())
