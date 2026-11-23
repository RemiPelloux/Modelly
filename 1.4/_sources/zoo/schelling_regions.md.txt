# Schelling segregation on real neighbourhoods

**Field:** sociology · **Zoo name:** `schelling_regions` · **Module:** `modelly.zoo.schelling_regions.model`

![Dissimilarity index over time for three thresholds](../images/gallery/schelling_regions.png)

Schelling's model with census tracts in place of grid cells: the 41 tracts of Chittenden
County, Vermont (bundled boundaries; see
[Geospatial models](../geospatial.md#real-data-samples)), each with the same number of
dwellings. Households of two groups fill a share `density` of the dwellings at random. A
household looks at the other households of its own tract and of the tracts that touch it (queen
contiguity) and is unhappy when fewer than `threshold` of them belong to its group. Every step
all unhappy households leave together and move into dwellings drawn at random among those then
free, the ones they just left included. The run stops when everybody is happy.

## How it is written

The households are two integer columns, tract and group. The neighbourhood counts of every tract
are one product, `(I + A) @ counts`, with `A` the tracts' adjacency from
`GeoSpace.contiguity("queen")`, so a step is a handful of array operations. Only the topology of
the real neighbourhoods is used: every tract has the same number of dwellings.

```python
from modelly.zoo.schelling_regions.model import (
    SchellingRegions,
    SchellingRegionsScenario,
)

model = SchellingRegions(SchellingRegionsScenario(rng=42))
model.run()
model.dissimilarity(), model.counts()  # households per (tract, group)
model.datacollector.get_model_vars_dataframe()  # dissimilarity, unhappy, moved per step
```

| Parameter | Default | Meaning |
|---|---|---|
| `capacity` | `20` | dwellings per tract |
| `density` | `0.9` | share of the dwellings occupied |
| `group_share` | `0.5` | share of the households in group 1 |
| `threshold` | `0.45` | least share of like households around a household for it to stay |
| `adjacency` | `None` | which tracts touch (0/1 matrix); the bundled tracts' queen contiguity when `None` |
| `steps` | `200` | maximum run length of `run()` |

Other regions: `SchellingRegionsScenario(adjacency=GeoSpace(regions).contiguity("rook"))`.

## Validation

There is no closed form for Schelling's model; its well-known result is qualitative: mild
preferences give strong segregation. Segregation is measured by Duncan's dissimilarity index,
the share of one group that would have to move for every tract to have the same mix.

`tests/zoo/test_schelling_regions.py` checks that the 41 tracts form one connected,
symmetric neighbourhood graph; that with `threshold = 0` nobody moves; that, for three seeds,
households content to be a slight minority (`threshold = 0.45`) end with a dissimilarity more
than five standard deviations above its value under random allocation (estimated from 30 random
allocations) and more than twice its mean; that the mean dissimilarity grows from threshold 0
to 0.3 to 0.5, ending above 0.9; that households and dwellings are conserved; and that the same
seed gives the same history.

## Data

U.S. Census Bureau, 2023 cartographic boundary files, public domain. The source and checksum
are in `modelly/space/geo/data/NOTICE.md`.

## References

- Schelling, T. C. (1971). Dynamic models of segregation. *Journal of Mathematical
  Sociology*, 1(2), 143-186.
- Duncan, O. D. and Duncan, B. (1955). A methodological analysis of segregation indexes.
  *American Sociological Review*, 20(2), 210-217.

Start a project from it with `modelly zoo copy schelling_regions my_schelling`.
