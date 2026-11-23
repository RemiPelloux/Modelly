# Schelling segregation on real neighbourhoods

**Field:** sociology · **Zoo name:** `schelling_regions` · **Module:** `modelly.zoo.schelling_regions.model`

![Dissimilarity index over time for three thresholds](https://remipelloux.github.io/Modelly/_images/schelling_regions.png)

Schelling’s model with census tracts in place of grid cells: the 41 tracts of Chittenden County, Vermont (bundled boundaries; see [Geospatial models](https://remipelloux.github.io/Modelly/geospatial.html#real-data-samples)), each with the same number of dwellings. Households of two groups fill a share `density` of the dwellings at random. A household looks at the other households of its own tract and of the tracts that touch it (queen contiguity) and is unhappy when fewer than `threshold` of them belong to its group. Every step all unhappy households leave together and move into dwellings drawn at random among those then free, the ones they just left included. The run stops when everybody is happy.

## How it is written

The households are two integer columns, tract and group. The neighbourhood counts of every tract are one product, `(I + A) @ counts`, with `A` the tracts’ adjacency from `GeoSpace.contiguity("queen")`, so a step is a handful of array operations. Only the topology of the real neighbourhoods is used: every tract has the same number of dwellings.

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

Parameter

Default

Meaning

capacity

20

dwellings per tract

density

0.9

share of the dwellings occupied

group_share

0.5

share of the households in group 1

threshold

0.45

least share of like households around a household for it to stay

adjacency

None

which tracts touch (0/1 matrix); the bundled tracts’ queen contiguity when None

steps

200

maximum run length of run()

Other regions: `SchellingRegionsScenario(adjacency=GeoSpace(regions).contiguity("rook"))`.

## Validation

There is no closed form for Schelling’s model; its well-known result is qualitative: mild preferences give strong segregation. Segregation is measured by Duncan’s dissimilarity index, the share of one group that would have to move for every tract to have the same mix.

`tests/zoo/test_schelling_regions.py` checks that the 41 tracts form one connected, symmetric neighbourhood graph; that with `threshold = 0` nobody moves; that, for three seeds, households content to be a slight minority (`threshold = 0.45`) end with a dissimilarity more than five standard deviations above its value under random allocation (estimated from 30 random allocations) and more than twice its mean; that the mean dissimilarity grows from threshold 0 to 0.3 to 0.5, ending above 0.9; that households and dwellings are conserved; and that the same seed gives the same history.

## Data

U.S. Census Bureau, 2023 cartographic boundary files, public domain. The source and checksum are in `modelly/space/geo/data/NOTICE.md`.

## Model card: Schelling segregation on real neighbourhoods

Schelling’s segregation model with census tracts in place of grid cells: households of two groups move between the 41 tracts of Chittenden County, Vermont, when too few of their neighbours are like them.

**Model:** `modelly.zoo.schelling_regions.model:SchellingRegions` · **Validated:** 2026-11-03 with Modelly 1.4.3, on source `55111a119d2e`

### Intended use

- Teaching Schelling’s result that mild preferences give strong segregation, on the topology of real neighbourhoods rather than a grid.
- A starting point for segregation models over other regions, by passing any tract adjacency (`GeoSpace(regions).contiguity(...)`).
- Comparing thresholds or group shares in relative terms through Duncan’s dissimilarity index.

### Out-of-scope use

- Describing or predicting segregation in Chittenden County or any real place: only the tracts’ adjacency is real; every tract has the same number of dwellings and the households are random.
- Explaining why real households move: the model has one preference rule and no prices, incomes, housing markets or discrimination.
- Judging any group, tract or community from its results.

### Data

- The 41 census tracts of Chittenden County, Vermont, bundled from the U.S. Census Bureau’s 2023 cartographic boundary file (public domain); source and checksum in `modelly/space/geo/data/NOTICE.md`.
- Only their queen contiguity is used; capacity, density, group share and threshold are illustrative values in `SchellingRegionsScenario`.

### Validation

Check

Test

with threshold 0 nobody moves and the allocation never changes

tests/zoo/test_schelling_regions.py::test_no_preference_no_moves

at threshold 0.45, for three seeds, the final dissimilarity is more than five standard deviations above random allocation (30 random allocations) and more than twice its mean

tests/zoo/test_schelling_regions.py::test_mild_preferences_segregate

mean dissimilarity grows from threshold 0 to 0.3 to 0.5, ending above 0.9

tests/zoo/test_schelling_regions.py::test_segregation_grows_with_the_threshold

the 41 tracts form one connected, symmetric neighbourhood graph; households and dwellings are conserved; same seed, same moves

tests/zoo/test_schelling_regions.py

### Known limits

- Every tract has the same number of dwellings; real tract sizes and populations are ignored.
- A household sees all households of its own and adjacent tracts with equal weight, and all unhappy households move at once into random free dwellings, at no cost.
- Two groups only, with one shared threshold; the run stops when everybody is happy, which says nothing about real time scales.
- There is no closed form: validation is qualitative (segregation far above random allocation), not a quantitative match.

### Ethical considerations

- The tracts are real neighbourhoods where real people live; results must not be read as a statement about their residents or how they choose where to live.
- Segregation results can be taken to blame one group or to suggest that segregation is natural or harmless; present them as the outcome of a toy preference rule, with the assumptions above.

## References

- Schelling, T. C. (1971). Dynamic models of segregation. *Journal of Mathematical Sociology*, 1(2), 143-186.
- Duncan, O. D. and Duncan, B. (1955). A methodological analysis of segregation indexes. *American Sociological Review*, 20(2), 210-217.

Start a project from it with `modelly zoo copy schelling_regions my_schelling`.
