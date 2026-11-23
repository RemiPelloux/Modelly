# Individual-based population with energy budgets

**Field:** ecology · **Zoo name:** `energy_budget` · **Module:** `modelly.zoo.energy_budget.model`

![Population size against the carrying capacity](https://remipelloux.github.io/Modelly/dev/_images/energy_budget.png)

Foragers walk a grid on which a resource flows in at a constant rate per cell. Every step each forager moves to a random neighbouring cell, the foragers in a cell share its resource equally and turn it into energy with an assimilation `efficiency`, and each pays a metabolic `cost`. A forager whose energy reaches `birth_threshold` splits it with an offspring in its cell; one whose energy falls below zero starves. Nothing but energy regulates the population.

## How it is written

Foragers keep their `energy` and the row of their cell in `Column` arrays and are placed by row (`CellIndex.track`), so no cell keeps a list of agents. Moving is `CellIndex.random_neighbor`, sharing is `CellIndex.counts`, starving is `ColumnTable.remove_where`; only births create objects (`ColumnTable.do_where`).

```python
from modelly.zoo.energy_budget.model import EnergyBudget, EnergyScenario

model = EnergyBudget(EnergyScenario(rng=42))
model.run()
model.population(), model.carrying_capacity()
model.datacollector.get_model_vars_dataframe()  # foragers and uneaten resource per step
```

Parameter

Default

Meaning

width, height

30, 30

grid size in cells

initial

100

foragers at the start

initial_energy

5.0

energy of each initial forager

inflow

1.0

resource added to every cell per step

efficiency

0.5

share of the eaten resource turned into energy

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

The resource is never capped and is eaten whenever a forager visits, so in the long run all of it is eaten. At equilibrium the energy assimilated equals the energy spent, `efficiency * inflow * cells = cost * N`, which gives the carrying capacity `K = efficiency * inflow * cells / cost` (450 with the defaults). The only other energy leaving the balance is the deficit of starving foragers, at most one `cost` each, which keeps the mean population at or slightly above `K`.

`tests/zoo/test_energy_budget.py` checks, for three seeds and two inflows, that the mean population after a burn-in of 150 steps is within 3 % of `K` (the step-to-step fluctuation is about 2 % of `K`, and averaging 250 steps leaves well under 1 %); that the uneaten stock stays bounded; that the population dies out without inflow; and that the same seed gives the same population curve.

## Model card: Individual-based population with energy budgets

Foragers that walk a resource grid, eat, pay a metabolic cost, reproduce by splitting their energy and starve, so the energy balance sets the carrying capacity.

**Model:** `modelly.zoo.energy_budget.model:EnergyBudget` · **Validated:** 2026-11-03 with Modelly 1.4.3, on source `9fb0746f6abe`

### Intended use

- Teaching how an energy budget regulates an individual-based population, and how the carrying capacity follows from inflow, efficiency and cost.
- A starting point for individual-based ecology models with a validated energy core to extend (age, spatial variation in inflow, predators).
- Comparing in relative terms how resource inflow, assimilation efficiency or metabolic cost move the equilibrium population.

### Out-of-scope use

- Predicting the abundance of a real species: the parameters are illustrative and nothing is calibrated.
- Management decisions such as harvest or stocking levels for a real population.
- Questions that depend on age, sex, size or behaviour beyond a random walk, none of which the foragers have.

### Data

- None by default: the 30 x 30 grid, the inflow, efficiency, cost and birth threshold are illustrative values in `EnergyScenario`.

### Validation

Check

Test

mean population after a burn-in of 150 steps is within 3 % of the carrying capacity from the energy balance (three seeds, two inflows)

tests/zoo/test_energy_budget.py::test_equilibrium_density_is_the_carrying_capacity

after the burn-in the uneaten resource stock does not grow: its mean over the second half is within 5 % of the first half

tests/zoo/test_energy_budget.py::test_resource_stock_stays_bounded

without inflow the population dies out; energy columns stay in range and follow the agents; same seed, same population curve

tests/zoo/test_energy_budget.py

### Known limits

- Foragers move to a random neighbouring cell every step and do not seek food; the foragers in a cell share its resource equally.
- The resource is never capped and is eaten whenever a forager visits, which is what makes the long-run intake equal the inflow.
- Reproduction is a split of energy at a fixed threshold, with no age, mates or maturation; death comes only from starvation.
- The validation checks the mean population against the carrying capacity, not the size or period of fluctuations around it.

### Ethical considerations

- This is a teaching model with no real population behind it; results carry no direct consequences for people, but say it is illustrative if they are used to argue about a real population.

## References

- Grimm, V. and Railsback, S. F. (2005). *Individual-based Modeling and Ecology*. Princeton University Press.

Start a project from it with `modelly zoo copy energy_budget my_population`.
