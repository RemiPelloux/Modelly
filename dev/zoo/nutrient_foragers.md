# Foragers on a diffusing nutrient field

**Field:** ecology · **Zoo name:** `nutrient_foragers` · **Module:** `modelly.zoo.nutrient_foragers.model`

![Foragers and nutrient per cell against the distance from the river](https://remipelloux.github.io/Modelly/dev/_images/nutrient_foragers.png)

A nutrient enters a closed landscape along its western edge (a river bank, say) at `supply` per edge cell per step, diffuses with coefficient `diffusion` and decays at rate `decay`. Foragers walk the grid at random. Every step each moves to a random neighbouring cell, the foragers in a cell share its nutrient, up to an `appetite` each, and turn it into energy with an assimilation `efficiency`; each pays a metabolic `cost`. A forager whose energy reaches `birth_threshold` splits it with an offspring; one whose energy falls below zero starves. Foragers crowd near the river, and their density falls inland with the nutrient’s.

## How it is written

The nutrient is a [`Field`](https://remipelloux.github.io/Modelly/dev/coupling.html) on the grid’s `nutrient` property layer, so `cell.nutrient` reads it, and it diffuses on its own explicit sub-steps (half the stability limit `1 / (4 D)`, four per step with the defaults). A `Coupling` runs two phases every step:

Phase

Component

Reads

Writes

0

Phase(model.forage)

nutrient

nutrient_input

1

Field("nutrient")

nutrient_input

nutrient

The foragers never write the layer: they write `nutrient_input`, the supply minus what they ate in each cell, and the field adds it before it diffuses. Foragers keep their `energy` and cell row in `Column` arrays and are placed by row (`CellIndex.track`), as in [energy budgets](https://remipelloux.github.io/Modelly/dev/zoo/energy_budget.html).

```python
from modelly.zoo.nutrient_foragers.model import NutrientForagers, NutrientScenario

model = NutrientForagers(NutrientScenario(rng=42))
model.run()
model.population(), model.carrying_capacity()
model.density_by_column()  # foragers per cell, west to east
model.field.total(), model.field.added, model.field.decayed  # the nutrient budget
```

Parameter

Default

Meaning

width, height

20, 20

grid size in cells

initial

200

foragers at the start

initial_energy

5.0

energy of each initial forager

supply

40.0

nutrient entering each western edge cell per step

diffusion

2.0

diffusion coefficient, cells squared per step

decay

0.0

decay rate of the nutrient per step

appetite

3.0

most nutrient a forager eats in a step

efficiency

0.5

share of the eaten nutrient turned into energy

cost

1.0

energy spent per forager per step

birth_threshold

10.0

energy at which a forager splits with an offspring

steps

400

run length of run()

## Validation

The field’s budget closes exactly: with closed walls nothing leaves, so the nutrient on the grid is what was supplied, minus what was eaten, minus what decayed, to round-off. At equilibrium the stock is stationary, so the foragers eat what enters minus what decays, and what they assimilate is what they spend: `efficiency * (supply_total - decayed) = cost * N`. Without decay this is the carrying capacity `K = efficiency * supply * height / cost` (400 with the defaults), however far the nutrient has to diffuse. The deficit of starving foragers, at most one `cost` each, lifts the mean about 1 % above it.

`tests/zoo/test_nutrient_foragers.py` checks, for three seeds, that the mean population after a burn-in of 150 steps is within 3 % of `K`; for two seeds and two decay rates that it is within 1 % of the balance with the measured decay and starvation deficit; that the nutrient budget closes to round-off; that the density near the river is ten times that of the eastern half; that a run resumed from a checkpoint is identical, bit for bit, to a straight one; and that the same seed gives the same run.

## Model card: Foragers on a diffusing nutrient field

Foragers eat from a nutrient that enters along a river bank, diffuses inland and decays, coupled to the field so that the energy balance sets the carrying capacity.

**Model:** `modelly.zoo.nutrient_foragers.model:NutrientForagers` · **Validated:** 2026-11-03 with Modelly 1.4.3, on source `7f21d20f4ad3`

### Intended use

- Teaching how agents couple to a diffusing field: the foragers’ phase writes what was eaten, the field adds it and diffuses one phase later.
- Showing how the energy balance sets a carrying capacity that does not depend on how far the nutrient diffuses, and how decay takes its share.
- A starting point for consumer-resource models on a spatial field, with a closed nutrient budget to keep when extending it.

### Out-of-scope use

- Predicting real nutrient concentrations or consumer densities along a river: the supply, diffusion and decay are illustrative and nothing is calibrated.
- Water-quality or land-management decisions for a real catchment.
- Systems where the nutrient is carried by flow (advection) or leaves through the boundaries: the landscape is closed and the field only diffuses and decays.

### Data

- None by default: the 20 x 20 grid, the supply along the western edge, the diffusion coefficient and the forager parameters are illustrative values in `NutrientScenario`.

### Validation

Check

Test

without decay, the mean population after a burn-in of 150 steps is within 3 % of the carrying capacity (three seeds)

tests/zoo/test_nutrient_foragers.py::test_population_settles_at_the_carrying_capacity

the mean population is within 1 % of the energy balance with the measured decay and starvation deficit (two seeds, two decay rates)

tests/zoo/test_nutrient_foragers.py::test_energy_balance_with_decay

the nutrient budget closes to round-off: on the grid is what was added minus what decayed, and added is supply minus eaten

tests/zoo/test_nutrient_foragers.py::test_nutrient_budget_closes_to_round_off

density near the river is over ten times that of the eastern half; a resumed checkpoint is identical; same seed, same run

tests/zoo/test_nutrient_foragers.py

### Known limits

- Foragers move to a random neighbouring cell and do not climb the nutrient gradient; the density pattern comes from the field alone.
- The nutrient enters only along the western edge at a constant rate, with closed walls elsewhere and no seasonality.
- Reproduction is a split of energy at a fixed threshold, with no age or maturation; death comes only from starvation.
- The validation checks the mean population against the energy balance, not the size of fluctuations or the transient approach to it.

### Ethical considerations

- This is a teaching model with no real system behind it; results carry no direct consequences for people, but say it is illustrative if they are used to argue about a real river or population.

## References

- Grimm, V. and Railsback, S. F. (2005). *Individual-based Modeling and Ecology*. Princeton University Press.
- Okubo, A. and Levin, S. A. (2001). *Diffusion and Ecological Problems: Modern Perspectives*, 2nd ed. Springer.

Start a project from it with `modelly zoo copy nutrient_foragers my_foragers`.
