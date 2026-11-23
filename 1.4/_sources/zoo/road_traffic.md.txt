# Traffic assignment on a real street network

**Field:** transport · **Zoo name:** `road_traffic` · **Module:** `modelly.zoo.road_traffic.model`

![Simulated street flows against their expectation from the edge betweenness](../images/gallery/road_traffic.png)

Trips between random junctions of the drivable streets of downtown Burlington, Vermont, from
OpenStreetMap (bundled; see [Geospatial models](../geospatial.md#real-data-samples)). Every step
`trips` travellers each draw an origin and a different destination uniformly among the 255
junctions and drive a shortest path by length, one-way streets respected. The model counts
the vehicles on every street segment: all-or-nothing assignment, the assignment step of the
classic four-step transport model, here with uniform demand.

## How it is written

The streets are a `modelly.space.geo.RoadNetwork`. Every shortest path is computed once, with
scipy's Dijkstra from every junction, and kept as a shortest-path tree per origin. A step counts
the trips per (origin, destination) and pushes the counts from each destination back towards its
origin along the trees, farthest junction first, for all origins at once: one vectorised pass
over the junctions per step, whatever the number of trips. The model holds `n x n` arrays, which
suits networks of up to a few thousand junctions.

```python
from modelly.zoo.road_traffic.model import RoadTraffic, RoadTrafficScenario

model = RoadTraffic(RoadTrafficScenario(rng=42))
model.run()
dict(zip(model.edge_labels(), model.flows))  # vehicles per (from, to) segment
model.datacollector.get_model_vars_dataframe()  # trips, mean trip length, busiest segment
```

| Parameter | Default | Meaning |
|---|---|---|
| `trips` | `500` | trips started every step |
| `weight` | `"length"` | the edge attribute shortest paths minimise (metres) |
| `roads` | `None` | a `RoadNetwork`; the bundled Burlington streets when `None` (`geo` extra) |
| `steps` | `20` | run length of `run()` |

Any strongly connected street graph works: `RoadTrafficScenario(roads=RoadNetwork(graph))`,
for example a graph saved with `osmnx.save_graphml` after `download_osm`.

## Validation

A trip from `s` to `t` uses segment `e` exactly when `e` is on the shortest path from `s` to
`t`. After `T` trips the flow on `e` is therefore binomial with mean `T * B(e) / (n (n - 1))`,
where `B(e)` is the number of ordered pairs whose shortest path uses `e`: the edge betweenness of
Girvan and Newman, computed by Brandes' algorithm.

`tests/zoo/test_road_traffic.py` checks that `betweenness()` equals NetworkX's
`edge_betweenness_centrality` (an independent implementation) on every one of the 607
segments, and that its total is the number of segments on all shortest paths; that, for three
seeds, every simulated flow is within five binomial standard deviations of its expectation and
segments on no shortest path carry nothing; that the distances are NetworkX's and that one-way
streets make some trips longer than the way back; that a network with unreachable junctions is
refused; and that the same seed gives the same flows.

## Data

© OpenStreetMap contributors. The streets are a derived database of OpenStreetMap data, under
the Open Database License 1.0; their source and checksum are in
`modelly/space/geo/data/NOTICE.md`.

## References

- Brandes, U. (2001). A faster algorithm for betweenness centrality. *Journal of Mathematical
  Sociology*, 25(2), 163-177.
- Girvan, M. and Newman, M. E. J. (2002). Community structure in social and biological
  networks. *Proceedings of the National Academy of Sciences*, 99(12), 7821-7826.
- Ortuzar, J. de D. and Willumsen, L. G. (2011). *Modelling Transport*, 4th ed. Wiley.

Start a project from it with `modelly zoo copy road_traffic my_traffic`.
