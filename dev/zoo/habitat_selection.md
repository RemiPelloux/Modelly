# Habitat selection on a real land-cover raster

**Field:** ecology · **Zoo name:** `habitat_selection` · **Module:** `modelly.zoo.habitat_selection.model`

![Share of the animals per land-cover class converging to the stationary law](https://remipelloux.github.io/Modelly/dev/_images/habitat_selection.png)

Animals disperse over a land-cover raster and settle where the habitat suits them. Each land-cover class has a preference weight `w`. Every step each animal proposes a jump to a cell drawn uniformly from the square of side `2 * radius + 1` around it and takes it with probability `min(1, w(new) / w(old))`; a jump off the raster is refused. The default raster is a 120 x 120 pixel window of ESA WorldCover 2021 (10 m pixels) over the Intervale in Burlington, Vermont (bundled; see [Geospatial models](https://remipelloux.github.io/Modelly/dev/geospatial.html#real-data-samples)): tree cover, grassland, cropland, built-up land, the Winooski River and wetland. The default weights describe a woodland species; they are illustrative, not fitted to any species.

## How it is written

The animals are independent, so their positions are two integer columns, updated in one vectorised pass per step. The raster is a plain array shaped like a grid, `(width, height)`; any `RasterLayer`’s `values` can replace it.

```python
from modelly.space.geo import RasterLayer
from modelly.zoo.habitat_selection.model import HabitatScenario, HabitatSelection

model = HabitatSelection(HabitatScenario(rng=42))
model.run()
model.classes, model.shares(), model.stationary_shares()

cover = RasterLayer.from_file("landcover.tif").values
other = HabitatSelection(HabitatScenario(rng=42, cover=cover))
```

Parameter

Default

Meaning

animals

5000

number of animals

radius

8

the largest jump along each axis, in cells

preferences

woodland weights

(class value, weight) pairs; classes not listed weigh 0

cover

None

land-cover classes, shape (width, height); the bundled WorldCover window when None

start_at_law

False

start at the stationary law instead of uniformly on the habitable cells

steps

400

run length of run()

## Validation

The proposal is symmetric and the acceptance is the Metropolis rule, so the walk satisfies detailed balance with `pi(cell)` proportional to `w(cell)`, and, the habitable cells being connected through jumps, it converges to it. At stationarity the share of animals on class `c` is `w_c n_c / sum_k w_k n_k`, with `n_c` the number of cells of class `c`: the resource-selection-function view of habitat use.

`tests/zoo/test_habitat_selection.py` starts 20,000 animals uniformly on the habitable cells, where the shares are more than 0.2 away from the law, and checks for three seeds that after 400 steps every class share is within five multinomial standard deviations of `w_c n_c / sum_k w_k n_k`. It also checks that a population started at the law stays within that bound at every step, that a class of weight 0 (permanent water) is never entered, that equal weights give the shares of the raster’s area, and that the same seed gives the same walk.

## Data

© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium, under CC BY 4.0. The window’s source and checksum are in `modelly/space/geo/data/NOTICE.md`.

## Model card: Habitat selection on a real land-cover raster

Animals disperse over a land-cover raster by a Metropolis rule weighted by a preference per land-cover class, and settle in proportion to habitat quality and area.

**Model:** `modelly.zoo.habitat_selection.model:HabitatSelection` · **Validated:** 2026-11-03 with Modelly 1.4.3, on source `fe74764fc237`

### Intended use

- Teaching the link between movement and habitat use: a Metropolis walk whose stationary law is the resource-selection-function view of occupancy.
- A starting point for dispersal models on real land cover, with any `RasterLayer`’s values in place of the bundled window.
- Comparing in relative terms how preference weights and jump radius change occupancy across land-cover classes.

### Out-of-scope use

- Predicting where a real species lives: the default weights describe an illustrative woodland species and are not fitted to any species.
- Conservation or land-use decisions without preference weights estimated from data on the species in question.
- Questions about population dynamics, territories or interactions between animals: the animals are independent and never born or die.

### Data

- A bundled 120 x 120 window of ESA WorldCover 2021 at 10 m over the Intervale in Burlington, Vermont (CC BY 4.0, © ESA WorldCover project 2021); its source and checksum are in `modelly/space/geo/data/NOTICE.md`. Reading it needs the `geo` extra.
- Preference weights per class are illustrative values (`WOODLAND` in the model); any `(width, height)` land-cover array can replace the raster through `cover`.

### Validation

Check

Test

from a uniform start far from the law, every class share is within five multinomial standard deviations of the stationary law (three seeds)

tests/zoo/test_habitat_selection.py::test_uniform_start_converges_to_the_law

a population started at the law stays within that bound at every step

tests/zoo/test_habitat_selection.py::test_law_is_stationary

a class of weight 0 is never entered; equal weights give area shares; same seed, same walk

tests/zoo/test_habitat_selection.py

### Known limits

- Animals are independent: no density dependence, competition or social behaviour, so occupancy depends only on the weights and the cover.
- Movement is a symmetric jump within a square of side `2 * radius + 1` accepted by the Metropolis rule, not a model of real movement paths or barriers between cells.
- Weights depend on the land-cover class alone, not on distance to edges, patch size or neighbouring classes.
- The validation checks the stationary law, not how fast animals reach it on a given raster.

### Ethical considerations

- Occupancy maps can be read as statements about where a species needs protection; with illustrative weights they say nothing about any real species, so say so whenever they are shown.

## References

- Metropolis, N., Rosenbluth, A. W., Rosenbluth, M. N., Teller, A. H. and Teller, E. (1953). Equation of state calculations by fast computing machines. *Journal of Chemical Physics*, 21(6), 1087-1092.
- Manly, B. F. J., McDonald, L. L., Thomas, D. L., McDonald, T. L. and Erickson, W. P. (2002). *Resource Selection by Animals*, 2nd ed. Kluwer.
- Zanaga, D. et al. (2022). ESA WorldCover 10 m 2021 v200. Zenodo, doi:10.5281/zenodo.7254221.

Start a project from it with `modelly zoo copy habitat_selection my_habitat`.
