# Commuting City

Residents of a synthetic city drive to work and back along its streets. The model shows the
pieces of `modelly.space.geo` working together:

- **Zones** are polygons of a `GeoSpace` in a projected CRS (UTM zone 31N, metres). Nobody
  lives in the four central zones; they hold most of the jobs.
- **Residents** come from `synthesize_population`: per outer zone, an age-by-employment table
  fitted to census-style marginals, rounded to whole people. Workers get a home point drawn
  inside their zone with `GeoSpace.random_points`.
- **Streets** are a `RoadNetwork` built from a NetworkX lattice with node coordinates; the
  middle avenues are twice as fast. A workplace zone is drawn by a gravity rule over the
  free-flow travel times of `RoadNetwork.distance_matrix`.
- **Trips** follow `RoadNetwork.shortest_path` on the current travel times. After every trip
  each street's travel time follows its flow (the BPR function), so the next trip reroutes
  around the congestion.

Each step is one trip: odd steps go to work, even steps come home. The `DataCollector`
records the mean trip time, the number of streets over capacity and the number of people in
the centre.

Everything is generated, so the example runs offline. For a real city, read census zones
with `geopandas.read_file` and the streets with `modelly.space.geo.download_osm(place)`
(the `osm` extra), and keep the rest of the model.

## How to run

```bash
pip install "modelly-abm[geo]"
python -c "from modelly.examples.spatial.commuting_city.model import CommutingCity; m = CommutingCity(); m.run_for(10); print(m.datacollector.get_model_vars_dataframe())"
```

To save the residents for a GIS, call `model.space.to_file("commuters.geojson")` or
`model.space.to_file("zones.parquet", what="regions")`.
