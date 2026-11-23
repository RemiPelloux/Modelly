# Gallery

A figure from every model of the [zoo](https://remipelloux.github.io/Modelly/dev/zoo/index.html), each made by running the model with a fixed seed. The figures are drawn by `tools/gallery/make_figures.py`, one panel per model in `tools/gallery/panels/`; rerun it (`python tools/gallery/make_figures.py`, the same in bash and PowerShell) after changing a model.

## Live models

These three models run in your browser: Python, Modelly and the model load in the page with Pyodide when you press Start (14 MB the first time, 28 MB for forest fire, which needs scipy; cached afterwards), and nothing runs on a server. Each frame is a static export made by `modelly export-web` when the docs are built ([Modelly in the browser](https://remipelloux.github.io/Modelly/dev/browser.html)); open it in its own tab for more room.

**[Forest fire](https://remipelloux.github.io/Modelly/dev/zoo/forest_fire.html)** ([open](https://remipelloux.github.io/Modelly/dev/live/forest_fire/index.html)).

**[Schelling segregation](https://remipelloux.github.io/Modelly/dev/examples/basic/schelling.html)** ([open](https://remipelloux.github.io/Modelly/dev/live/schelling/index.html)).

**[Wolf-sheep predation](https://remipelloux.github.io/Modelly/dev/examples/advanced/wolf_sheep.html)** ([open](https://remipelloux.github.io/Modelly/dev/live/wolf_sheep/index.html)).

## Epidemiology

**[Age-structured SEIR](https://remipelloux.github.io/Modelly/dev/zoo/age_seir.html).** Children, with the most contacts, peak first and highest.

![Infectious share of three age groups over time](https://remipelloux.github.io/Modelly/dev/_images/age_seir.png)

**[Within-host and between-host epidemic](https://remipelloux.github.io/Modelly/dev/zoo/within_host.html).** Each host’s virus rises and clears on its own course while the outbreak passes through the population.

![Virus loads of five hosts infected at different times, and the share infectious](https://remipelloux.github.io/Modelly/dev/_images/within_host.png)

**[Vector-borne transmission](https://remipelloux.github.io/Modelly/dev/zoo/vector_borne.html).** Outbreaks grow with mosquito density, in the order of the Ross-Macdonald R0.

![Infectious hosts for three mosquito densities](https://remipelloux.github.io/Modelly/dev/_images/vector_borne.png)

**[Epidemic and hospital capacity](https://remipelloux.github.io/Modelly/dev/zoo/hospital_epidemic.html).** When contacts fall with the pressure on the hospital, occupancy peaks lower and later, and fewer surge beds open.

![Occupied and open beds over time, with and without the contact response](https://remipelloux.github.io/Modelly/dev/_images/hospital_epidemic.png)

## Ecology

**[Forest fire](https://remipelloux.github.io/Modelly/dev/zoo/forest_fire.html).** The burnt share jumps at the percolation threshold.

![Burnt share against tree density](https://remipelloux.github.io/Modelly/dev/_images/forest_fire.png)

**[Energy budgets](https://remipelloux.github.io/Modelly/dev/zoo/energy_budget.html).** After a boom and bust the population settles on the carrying capacity set by the energy balance.

![Population over time with its carrying capacity](https://remipelloux.github.io/Modelly/dev/_images/energy_budget.png)

**[Habitat selection](https://remipelloux.github.io/Modelly/dev/zoo/habitat_selection.html).** On real land cover, animals started uniformly settle in proportion to habitat preference (dashed: the stationary law).

![Share of the animals per land-cover class over time](https://remipelloux.github.io/Modelly/dev/_images/habitat_selection.png)

**[Foragers on a nutrient field](https://remipelloux.github.io/Modelly/dev/zoo/nutrient_foragers.html).** The nutrient diffuses inland from the river bank, and the foragers follow it.

![Foragers and nutrient per cell against the distance from the river](https://remipelloux.github.io/Modelly/dev/_images/nutrient_foragers.png)

## Economics

**[Order book](https://remipelloux.github.io/Modelly/dev/zoo/order_book.html).** Mid-price returns have fat tails compared with a normal distribution.

![Histogram of standardised returns on a log scale](https://remipelloux.github.io/Modelly/dev/_images/order_book.png)

**[Boltzmann wealth exchange](https://remipelloux.github.io/Modelly/dev/zoo/kinetic_wealth.html).** Random exchange of money gives the Boltzmann-Gibbs distribution.

![Wealth distribution against the exact stationary law](https://remipelloux.github.io/Modelly/dev/_images/kinetic_wealth.png)

**[Bouchaud-Mezard](https://remipelloux.github.io/Modelly/dev/zoo/bouchaud_mezard.html).** The Gini settles on the value of the inverse-gamma law, higher for noisier returns.

![Gini over time for three noise levels](https://remipelloux.github.io/Modelly/dev/_images/bouchaud_mezard.png)

## Sociology and political science

**[Deffuant](https://remipelloux.github.io/Modelly/dev/zoo/deffuant.html).** Opinions merge into a few clusters.

![Opinion trajectories](https://remipelloux.github.io/Modelly/dev/_images/deffuant.png)

**[Hegselmann-Krause](https://remipelloux.github.io/Modelly/dev/zoo/hegselmann_krause.html).** Final opinions against the confidence bound: many clusters, fewer, then consensus.

![Final opinions against the confidence bound](https://remipelloux.github.io/Modelly/dev/_images/hegselmann_krause.png)

**[Schelling on real neighbourhoods](https://remipelloux.github.io/Modelly/dev/zoo/schelling_regions.html).** On census tracts, households content to be a slight minority still end almost fully segregated.

![Dissimilarity index over time for three thresholds](https://remipelloux.github.io/Modelly/dev/_images/schelling_regions.png)

**[Axelrod](https://remipelloux.github.io/Modelly/dev/zoo/axelrod.html).** More traits per feature leave more cultural regions.

![Cultural regions against traits per feature](https://remipelloux.github.io/Modelly/dev/_images/axelrod.png)

## Transport and energy

**[Nagel-Schreckenberg](https://remipelloux.github.io/Modelly/dev/zoo/nagel_schreckenberg.html).** The fundamental diagram, with and without random braking.

![Flow against density for three dawdling probabilities](https://remipelloux.github.io/Modelly/dev/_images/nagel_schreckenberg.png)

**[Traffic assignment](https://remipelloux.github.io/Modelly/dev/zoo/road_traffic.html).** On real streets, every segment’s flow follows its edge betweenness.

![Simulated against expected vehicles per street segment](https://remipelloux.github.io/Modelly/dev/_images/road_traffic.png)

**[Bass diffusion](https://remipelloux.github.io/Modelly/dev/zoo/bass_diffusion.html).** Adoption follows the Bass curve when mixing is complete, and lags on a sparse network.

![Share adopted over time against the Bass equation](https://remipelloux.github.io/Modelly/dev/_images/bass_diffusion.png)

## Submit your model

The gallery is also open to community models built with Modelly that are not in the zoo. Open a pull request that adds your model’s entry to this page under a section “Community models”, with one PNG of at most 100 KB in `docs/images/gallery/community/`, and fill in the template below in the pull request description. A gallery entry does not need a validation test, but it must run from a seed and say how it was checked.

```text
Title:            one line
Author(s):        names, and an ORCID if you have one
Field:            epidemiology / ecology / economics / sociology / transport / energy / other
Repository:       a public URL with the code, a licence and a README
Modelly version:  the version it was run with (python -c "import modelly; print(modelly.__version__)")
Reference:        the paper or report it reproduces or supports, if any
What it shows:    two or three sentences
How to run it:    the command that makes the figure, with its seed
How it was checked: an analytical result, a published figure, a comparison with another
                    implementation, or a test in the repository
Runtime:          on a laptop, for the figure
```

The maintainers run the command before merging. Models that are validated, small and of general interest may be invited into the zoo.
