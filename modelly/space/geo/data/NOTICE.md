# Bundled geospatial samples: sources and licences

Three small extracts of Burlington, Vermont (United States), used by the zoo's real-data
models and by the tests, which run offline. They hold no personal data: street geometry,
land cover and administrative boundaries only. `scripts/geo_data.py` downloads the full
sources, checks their SHA-256 and cuts these extracts again.

## burlington_roads.graphml

The drivable streets (OpenStreetMap `highway` = primary to residential, and links) of
downtown Burlington, in the box 44.4700 to 44.4840 N, 73.2200 to 73.2000 W, as of
2026-10-01T00:00:00Z: an Overpass API query pinned to that date, retrieved 2026-10-27 from
<https://overpass-api.de/api/interpreter>. Ways are split at junctions, one-way streets
kept one-way, lengths are geodesic metres on WGS 84, and only the largest strongly
connected component is kept (255 nodes, 607 directed edges).

- **Licence:** Open Database License (ODbL) 1.0,
  <https://opendatacommons.org/licenses/odbl/1-0/>.
- **Attribution:** © OpenStreetMap contributors, <https://www.openstreetmap.org/copyright>.
- This file is a derived database of OpenStreetMap data and is itself available under the
  ODbL 1.0. Any adapted database you make from it must be offered under the ODbL as well.
- **Checksum** of the source: SHA-256 of its elements sorted by type and id, as compact JSON
  with sorted keys, `b4b86ccc29b9490e5ea00cd584582c412ccaf2a3abd2fedaf88fc392ce329c14`.

## burlington_landcover.tif

A 120 x 120 pixel window (10 m pixels, 1/12000 degree, north-west corner 73.215 W,
44.505 N, the Intervale) of the ESA WorldCover 10 m 2021 v200 tile N42W075, pixel values
unchanged (WorldCover classes: 10 tree cover, 20 shrubland, 30 grassland, 40 cropland,
50 built-up, 60 bare or sparse vegetation, 70 snow and ice, 80 permanent water, 90
herbaceous wetland, 95 mangroves, 100 moss and lichen; 0 is nodata). Source retrieved
2026-10-27 from
<https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N42W075_Map.tif>.

- **Licence:** Creative Commons Attribution 4.0 International (CC BY 4.0),
  <https://creativecommons.org/licenses/by/4.0/>.
- **Attribution:** © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel
  data (2021) processed by ESA WorldCover consortium. Zanaga, D. et al. (2022). ESA
  WorldCover 10 m 2021 v200. Zenodo, <https://doi.org/10.5281/zenodo.7254221>.
- **Changes:** cropped to the window above; recompressed.
- **Checksum** of the source tile:
  `6bc1b5a5e5c6a680cf4b3c19ef069f4dc817042fdb952862cefb128df5a322d6`.

## burlington_tracts.geojson

The 41 census tracts of Chittenden County, Vermont, from the U.S. Census Bureau's 2023
cartographic boundary file (1:500,000) for Vermont, reprojected from NAD83 to WGS 84 and
rounded to six decimals, with the columns `GEOID`, `NAME` and `ALAND` (land area, m²).
Source retrieved 2026-10-27 from
<https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_50_tract_500k.zip>.

- **Licence:** public domain. Works of the United States Government are not subject to
  copyright in the United States (17 U.S.C. § 105).
- **Attribution (courtesy):** U.S. Census Bureau, 2023 Cartographic Boundary Files.
- **Checksum** of the source archive:
  `049cfa9b968db3de27c15fa0dc2f52fcb96ad87c02881e7c66dc52644bade202`.
