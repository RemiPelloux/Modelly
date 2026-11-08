# Axelrod culture dissemination

**Field:** political science · **Zoo name:** `axelrod` · **Module:** `modelly.zoo.axelrod.model`

![Cultural regions against the number of traits](https://remipelloux.github.io/Modelly/dev/_images/axelrod.png)

Every site of a square grid holds a culture: `features` features, each one of `traits` values. At each event a random site and a random neighbour interact with probability equal to their overlap, the share of features on which they agree; when they do, the site copies one feature on which they differ. Similar neighbours grow more similar and neighbours with nothing in common never interact, so the grid freezes into regions of identical culture: one culture for few traits, many regions for many traits.

## How it is written

The sites are the rows of a `CellIndex` over an `OrthogonalVonNeumannGrid`, and the cultures one `(n_sites, features)` integer array. Events stay sequential, as in the original, but each step draws its sites, their neighbours (`CellIndex.random_neighbor`) and the uniforms in three numpy calls, then runs `events_per_step` events on plain lists. After each step the model checks every bond at once; when no pair with partial overlap is left the map is frozen and `running` turns `False`. Regions are the connected components of the bonds with full overlap (`scipy.sparse.csgraph`).

```python
from modelly.zoo.axelrod.model import Axelrod, AxelrodScenario

model = Axelrod(AxelrodScenario(rng=42, traits=15))
model.run()
model.n_regions(), model.time
```

Parameter

Default

Meaning

width, height

10, 10

grid size in sites

features

5

cultural features per site

traits

10

values each feature can take

events_per_step

2000

interactions attempted per step

steps

500

maximum run length of run()

## Validation

`tests/zoo/test_axelrod.py` runs the 10 x 10, five-feature model of the original paper to its absorbing state with five seeds. Two traits end in a single region for at least four seeds of five; thirty traits leave more than 25 regions in every run; the mean number of regions grows from two to fifteen to sixty traits. It also checks the absorbing state (every bond has overlap 0 or `features`), the interaction rule on hand-made pairs, and that the same seed gives the same culture map.

## Model card: Axelrod culture dissemination

Axelrod’s model of the dissemination of culture: sites of a grid copy traits from neighbours with a probability set by their similarity, until the map freezes into regions of identical culture.

**Model:** `modelly.zoo.axelrod.model:Axelrod` · **Validated:** 2026-11-03 with Modelly 1.4.3, on source `1698a96d5044`

### Intended use

- Teaching how local convergence can produce global polarisation: one culture for few traits per feature, many regions for many.
- Exploring the transition in the number of regions as traits, features or grid size change.
- A starting point for social-influence models with a validated core to extend (noise, media, other networks).

### Out-of-scope use

- Describing or predicting real cultures, opinions or political views: features and traits are abstract integers with no measured meaning.
- Drawing conclusions about real communities, migration or policy from the number or size of regions.

### Data

- None by default: cultures are drawn uniformly at random, and grid size, features and traits are illustrative values in `AxelrodScenario` (the 10 x 10, five-feature setting of the original paper).

### Validation

Check

Test

on the 10 x 10, five-feature grid, two traits end in a single region for at least four seeds of five

tests/zoo/test_axelrod.py::test_few_traits_end_in_monoculture

thirty traits leave more than 25 regions in every one of five runs

tests/zoo/test_axelrod.py::test_many_traits_leave_many_regions

the mean number of regions grows from two to fifteen to sixty traits

tests/zoo/test_axelrod.py::test_regions_grow_with_traits

in the frozen map every bond has overlap 0 or all features; the interaction rule on hand-made pairs; same seed, same culture map

tests/zoo/test_axelrod.py

### Known limits

- A small square grid without wrapping, von Neumann neighbours only: sites at the edge have fewer neighbours, and nobody moves.
- Traits are nominal and all features weigh the same; there is no noise, so the absorbing state is reached and kept for ever.
- Validation is qualitative, against the original paper’s regimes on a small grid; regions on larger grids and the exact transition point are not checked.

### Ethical considerations

- Results about polarisation or the persistence of minority cultures can be read as statements about real groups; present them as properties of an abstract rule, not of any society.

## References

- Axelrod, R. (1997). The dissemination of culture: a model with local convergence and global polarization. *Journal of Conflict Resolution*, 41(2), 203-226.
- Castellano, C., Marsili, M. and Vespignani, A. (2000). Nonequilibrium phase transition in a model for social influence. *Physical Review Letters*, 85(16), 3536-3539.

Start a project from it with `modelly zoo copy axelrod my_cultures`.
