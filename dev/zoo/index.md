# Model zoo

`modelly.zoo` holds reference models from many fields. Each one is a starting point for your own model, a teaching example and a regression test: it is written the way Modelly models are meant to be written (columns, cohorts and cell indexes where they fit), it has a `Scenario` with every parameter, its references are in its docstring, and a validation test in `tests/zoo` checks it against an analytical or a well-known result on every run of the local gate.

Model

Field

Validated against

[Age-structured SEIR](https://remipelloux.github.io/Modelly/dev/zoo/age_seir.html)

epidemiology

final-size relation, within its central-limit bound

[Within-host and between-host epidemic](https://remipelloux.github.io/Modelly/dev/zoo/within_host.html)

epidemiology

each host’s ODE equals its own solve_ivp call; analytic clearance time

[Vector-borne transmission](https://remipelloux.github.io/Modelly/dev/zoo/vector_borne.html)

epidemiology

outbreak size ordered like the Ross-Macdonald R0

[Habitat selection on real land cover](https://remipelloux.github.io/Modelly/dev/zoo/habitat_selection.html)

ecology

Metropolis stationary law of habitat use

[Epidemic and hospital capacity](https://remipelloux.github.io/Modelly/dev/zoo/hospital_epidemic.html)

epidemiology

final size; exact hospital solution; admissions mass balance

[Energy budgets](https://remipelloux.github.io/Modelly/dev/zoo/energy_budget.html)

ecology

carrying capacity from the energy balance

[Foragers on a nutrient field](https://remipelloux.github.io/Modelly/dev/zoo/nutrient_foragers.html)

ecology

carrying capacity; nutrient budget closed to round-off

[Forest fire and succession](https://remipelloux.github.io/Modelly/dev/zoo/forest_fire.html)

ecology

site-percolation threshold

[Order book](https://remipelloux.github.io/Modelly/dev/zoo/order_book.html)

economics

fat tails: positive excess kurtosis of returns

[Boltzmann wealth exchange](https://remipelloux.github.io/Modelly/dev/zoo/kinetic_wealth.html)

economics

exact stationary distribution and Gini

[Bouchaud-Mezard wealth](https://remipelloux.github.io/Modelly/dev/zoo/bouchaud_mezard.html)

economics

inverse-gamma law; Gini rising with the noise

[Deffuant opinions](https://remipelloux.github.io/Modelly/dev/zoo/deffuant.html)

sociology

consensus versus cluster count by confidence bound

[Hegselmann-Krause opinions](https://remipelloux.github.io/Modelly/dev/zoo/hegselmann_krause.html)

sociology

consensus versus cluster count by confidence bound

[Schelling on real neighbourhoods](https://remipelloux.github.io/Modelly/dev/zoo/schelling_regions.html)

sociology

segregation far above random allocation

[Axelrod culture](https://remipelloux.github.io/Modelly/dev/zoo/axelrod.html)

political science

cultural regions versus number of traits

[Nagel-Schreckenberg traffic](https://remipelloux.github.io/Modelly/dev/zoo/nagel_schreckenberg.html)

transport

fundamental diagram

[Traffic assignment on real streets](https://remipelloux.github.io/Modelly/dev/zoo/road_traffic.html)

transport

exact edge betweenness, binomial flows

[Bass diffusion on a network](https://remipelloux.github.io/Modelly/dev/zoo/bass_diffusion.html)

energy

Bass ODE in the well-mixed limit

The [gallery](https://remipelloux.github.io/Modelly/dev/gallery.html) shows a figure of each, and the [domain tutorials](https://remipelloux.github.io/Modelly/dev/tutorials/domains/index.html) build on them. Habitat selection, Schelling on real neighbourhoods and traffic assignment run on small real maps bundled with Modelly (see [Geospatial models](https://remipelloux.github.io/Modelly/dev/geospatial.html#zoo-models-on-real-data)) and need the `geo` extra.

## Using a zoo model

```python
from modelly.zoo import get

entry = get("age_seir")
AgeSEIR, SEIRScenario = entry.load()
model = AgeSEIR(SEIRScenario(rng=42, beta=0.05))
model.run()
frame = model.datacollector.get_model_vars_dataframe()
```

Every zoo model has `run()`, which runs the scenario’s `steps`, and a `datacollector`.

## From the command line

The commands are the same in bash and PowerShell.

```text
modelly zoo list                         every model, its field and a summary
modelly zoo list --field ecology         the models of one field
modelly zoo info forest_fire             parameters, validation and references
modelly zoo copy forest_fire my_forest   write my_forest/model.py and my_forest/README.md
```

`modelly zoo copy` writes the model’s single module, unchanged, into a new folder, with a README that shows how to run it. The copy imports only public `modelly` modules, so it runs as it is; change it as you like. Nothing is overwritten.

## Not included

- **Artificial Anasazi** (Long House Valley). Its validation is against the published population reconstruction, which needs the archaeological and paleo-environmental data of the original study. Building it with synthetic data would not validate anything, so it is not in the zoo.

## Contributing a model

A zoo model is a folder `modelly/zoo/<name>/` with a docstring-only `__init__.py` and a `model.py` that holds the `Scenario` and the `Model`, an entry in `modelly/zoo/registry.py`, a test `tests/zoo/test_<name>.py` with a validation and a determinism check, a page `docs/zoo/<name>.md` and a gallery panel `tools/gallery/panels/<name>.py`. Only cite a paper in the docstring if you have checked the reference. Community models that do not belong in the zoo go to the [gallery](https://remipelloux.github.io/Modelly/dev/gallery.html).
