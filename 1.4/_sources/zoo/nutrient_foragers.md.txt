# Foragers on a diffusing nutrient field

**Field:** ecology · **Zoo name:** `nutrient_foragers` · **Module:** `modelly.zoo.nutrient_foragers.model`

![Foragers and nutrient per cell against the distance from the river](../images/gallery/nutrient_foragers.png)

A nutrient enters a closed landscape along its western edge (a river bank, say) at `supply` per
edge cell per step, diffuses with coefficient `diffusion` and decays at rate `decay`. Foragers
walk the grid at random. Every step each moves to a random neighbouring cell, the foragers in a
cell share its nutrient, up to an `appetite` each, and turn it into energy with an assimilation
`efficiency`; each pays a metabolic `cost`. A forager whose energy reaches `birth_threshold`
splits it with an offspring; one whose energy falls below zero starves. Foragers crowd near the
river, and their density falls inland with the nutrient's.

## How it is written

The nutrient is a [`Field`](../coupling.md) on the grid's `nutrient` property layer, so
`cell.nutrient` reads it, and it diffuses on its own explicit sub-steps (half the stability
limit `1 / (4 D)`, four per step with the defaults). A `Coupling` runs two phases every step:

| Phase | Component | Reads | Writes |
|---|---|---|---|
| 0 | `Phase(model.forage)` | `nutrient` | `nutrient_input` |
| 1 | `Field("nutrient")` | `nutrient_input` | `nutrient` |

The foragers never write the layer: they write `nutrient_input`, the supply minus what they ate
in each cell, and the field adds it before it diffuses. Foragers keep their `energy` and cell
row in `Column` arrays and are placed by row (`CellIndex.track`), as in
[energy budgets](energy_budget.md).

```python
from modelly.zoo.nutrient_foragers.model import NutrientForagers, NutrientScenario

model = NutrientForagers(NutrientScenario(rng=42))
model.run()
model.population(), model.carrying_capacity()
model.density_by_column()  # foragers per cell, west to east
model.field.total(), model.field.added, model.field.decayed  # the nutrient budget
```

| Parameter | Default | Meaning |
|---|---|---|
| `width`, `height` | `20`, `20` | grid size in cells |
| `initial` | `200` | foragers at the start |
| `initial_energy` | `5.0` | energy of each initial forager |
| `supply` | `40.0` | nutrient entering each western edge cell per step |
| `diffusion` | `2.0` | diffusion coefficient, cells squared per step |
| `decay` | `0.0` | decay rate of the nutrient per step |
| `appetite` | `3.0` | most nutrient a forager eats in a step |
| `efficiency` | `0.5` | share of the eaten nutrient turned into energy |
| `cost` | `1.0` | energy spent per forager per step |
| `birth_threshold` | `10.0` | energy at which a forager splits with an offspring |
| `steps` | `400` | run length of `run()` |

## Validation

The field's budget closes exactly: with closed walls nothing leaves, so the nutrient on the
grid is what was supplied, minus what was eaten, minus what decayed, to round-off. At
equilibrium the stock is stationary, so the foragers eat what enters minus what decays, and
what they assimilate is what they spend: `efficiency * (supply_total - decayed) = cost * N`.
Without decay this is the carrying capacity `K = efficiency * supply * height / cost` (400 with
the defaults), however far the nutrient has to diffuse. The deficit of starving foragers, at
most one `cost` each, lifts the mean about 1 % above it.

`tests/zoo/test_nutrient_foragers.py` checks, for three seeds, that the mean population after a
burn-in of 150 steps is within 3 % of `K`; for two seeds and two decay rates that it is within
1 % of the balance with the measured decay and starvation deficit; that the nutrient budget
closes to round-off; that the density near the river is ten times that of the eastern half;
that a run resumed from a checkpoint is identical, bit for bit, to a straight one; and that the
same seed gives the same run.

## References

- Grimm, V. and Railsback, S. F. (2005). *Individual-based Modeling and Ecology*. Princeton
  University Press.
- Okubo, A. and Levin, S. A. (2001). *Diffusion and Ecological Problems: Modern Perspectives*,
  2nd ed. Springer.

Start a project from it with `modelly zoo copy nutrient_foragers my_foragers`.
