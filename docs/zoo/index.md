# Model zoo

`modelly.zoo` holds reference models from many fields. Each one is a starting point for your
own model, a teaching example and a regression test: it is written the way Modelly models are
meant to be written (columns, cohorts and cell indexes where they fit), it has a `Scenario`
with every parameter, its references are in its docstring, and a validation test in
`tests/zoo` checks it against an analytical or a well-known result on every run of the local
gate.

| Model | Field | Validated against |
|---|---|---|
| [Age-structured SEIR](age_seir.md) | epidemiology | final-size relation, within its central-limit bound |
| [Vector-borne transmission](vector_borne.md) | epidemiology | outbreak size ordered like the Ross-Macdonald R0 |
| [Epidemic and hospital capacity](hospital_epidemic.md) | epidemiology | final size; exact hospital solution; admissions mass balance |
| [Energy budgets](energy_budget.md) | ecology | carrying capacity from the energy balance |
| [Foragers on a nutrient field](nutrient_foragers.md) | ecology | carrying capacity; nutrient budget closed to round-off |
| [Forest fire and succession](forest_fire.md) | ecology | site-percolation threshold |
| [Order book](order_book.md) | economics | fat tails: positive excess kurtosis of returns |
| [Boltzmann wealth exchange](kinetic_wealth.md) | economics | exact stationary distribution and Gini |
| [Bouchaud-Mezard wealth](bouchaud_mezard.md) | economics | inverse-gamma law; Gini rising with the noise |
| [Deffuant opinions](deffuant.md) | sociology | consensus versus cluster count by confidence bound |
| [Hegselmann-Krause opinions](hegselmann_krause.md) | sociology | consensus versus cluster count by confidence bound |
| [Axelrod culture](axelrod.md) | political science | cultural regions versus number of traits |
| [Nagel-Schreckenberg traffic](nagel_schreckenberg.md) | transport | fundamental diagram |
| [Bass diffusion on a network](bass_diffusion.md) | energy | Bass ODE in the well-mixed limit |

The [gallery](../gallery.md) shows a figure of each, and the
[domain tutorials](../tutorials/domains/index.md) build on them.

## Using a zoo model

```python
from modelly.zoo import get

entry = get("age_seir")
AgeSEIR, SEIRScenario = entry.load()
model = AgeSEIR(SEIRScenario(rng=42, beta=0.05))
model.run()
frame = model.datacollector.get_model_vars_dataframe()
```

Every zoo model has `run()`, which runs the scenario's `steps`, and a `datacollector`.

## From the command line

The commands are the same in bash and PowerShell.

```text
modelly zoo list                         every model, its field and a summary
modelly zoo list --field ecology         the models of one field
modelly zoo info forest_fire             parameters, validation and references
modelly zoo copy forest_fire my_forest   write my_forest/model.py and my_forest/README.md
```

`modelly zoo copy` writes the model's single module, unchanged, into a new folder, with a
README that shows how to run it. The copy imports only public `modelly` modules, so it runs
as it is; change it as you like. Nothing is overwritten.

## Not included

- **Artificial Anasazi** (Long House Valley). Its validation is against the published
  population reconstruction, which needs the archaeological and paleo-environmental data of
  the original study. Building it with synthetic data would not validate anything, so it is
  not in the zoo.
- **Schelling with real neighbourhoods** needs census geometries; the classic Schelling
  model is in the [examples](../examples.md).

## Contributing a model

A zoo model is a folder `modelly/zoo/<name>/` with a docstring-only `__init__.py` and a
`model.py` that holds the `Scenario` and the `Model`, an entry in
`modelly/zoo/registry.py`, a test `tests/zoo/test_<name>.py` with a validation and a
determinism check, a page `docs/zoo/<name>.md` and a gallery panel
`tools/gallery/panels/<name>.py`. Only cite a paper in the docstring if you have checked the
reference. Community models that do not belong in the zoo go to the
[gallery](../gallery.md).

```{toctree}
:hidden: true

age_seir
vector_borne
hospital_epidemic
energy_budget
nutrient_foragers
forest_fire
order_book
kinetic_wealth
bouchaud_mezard
deffuant
hegselmann_krause
axelrod
nagel_schreckenberg
bass_diffusion
```
