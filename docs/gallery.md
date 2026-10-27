# Gallery

A figure from every model of the [zoo](zoo/index.md), each made by running the model with a
fixed seed. The figures are drawn by `tools/gallery/make_figures.py`, one panel per model in
`tools/gallery/panels/`; rerun it (`python tools/gallery/make_figures.py`, the same in bash
and PowerShell) after changing a model.

## Epidemiology

**[Age-structured SEIR](zoo/age_seir.md).** Children, with the most contacts, peak first and
highest.

![Infectious share of three age groups over time](images/gallery/age_seir.png)

**[Vector-borne transmission](zoo/vector_borne.md).** Outbreaks grow with mosquito density,
in the order of the Ross-Macdonald R0.

![Infectious hosts for three mosquito densities](images/gallery/vector_borne.png)

**[Epidemic and hospital capacity](zoo/hospital_epidemic.md).** When contacts fall with the
pressure on the hospital, occupancy peaks lower and later, and fewer surge beds open.

![Occupied and open beds over time, with and without the contact response](images/gallery/hospital_epidemic.png)

## Ecology

**[Forest fire](zoo/forest_fire.md).** The burnt share jumps at the percolation threshold.

![Burnt share against tree density](images/gallery/forest_fire.png)

**[Energy budgets](zoo/energy_budget.md).** After a boom and bust the population settles on
the carrying capacity set by the energy balance.

![Population over time with its carrying capacity](images/gallery/energy_budget.png)

**[Habitat selection](zoo/habitat_selection.md).** On real land cover, animals started
uniformly settle in proportion to habitat preference (dashed: the stationary law).

![Share of the animals per land-cover class over time](images/gallery/habitat_selection.png)

**[Foragers on a nutrient field](zoo/nutrient_foragers.md).** The nutrient diffuses inland from
the river bank, and the foragers follow it.

![Foragers and nutrient per cell against the distance from the river](images/gallery/nutrient_foragers.png)

## Economics

**[Order book](zoo/order_book.md).** Mid-price returns have fat tails compared with a
normal distribution.

![Histogram of standardised returns on a log scale](images/gallery/order_book.png)

**[Boltzmann wealth exchange](zoo/kinetic_wealth.md).** Random exchange of money gives the
Boltzmann-Gibbs distribution.

![Wealth distribution against the exact stationary law](images/gallery/kinetic_wealth.png)

**[Bouchaud-Mezard](zoo/bouchaud_mezard.md).** The Gini settles on the value of the
inverse-gamma law, higher for noisier returns.

![Gini over time for three noise levels](images/gallery/bouchaud_mezard.png)

## Sociology and political science

**[Deffuant](zoo/deffuant.md).** Opinions merge into a few clusters.

![Opinion trajectories](images/gallery/deffuant.png)

**[Hegselmann-Krause](zoo/hegselmann_krause.md).** Final opinions against the confidence
bound: many clusters, fewer, then consensus.

![Final opinions against the confidence bound](images/gallery/hegselmann_krause.png)

**[Schelling on real neighbourhoods](zoo/schelling_regions.md).** On census tracts, households
content to be a slight minority still end almost fully segregated.

![Dissimilarity index over time for three thresholds](images/gallery/schelling_regions.png)

**[Axelrod](zoo/axelrod.md).** More traits per feature leave more cultural regions.

![Cultural regions against traits per feature](images/gallery/axelrod.png)

## Transport and energy

**[Nagel-Schreckenberg](zoo/nagel_schreckenberg.md).** The fundamental diagram, with and
without random braking.

![Flow against density for three dawdling probabilities](images/gallery/nagel_schreckenberg.png)

**[Traffic assignment](zoo/road_traffic.md).** On real streets, every segment's flow follows
its edge betweenness.

![Simulated against expected vehicles per street segment](images/gallery/road_traffic.png)

**[Bass diffusion](zoo/bass_diffusion.md).** Adoption follows the Bass curve when mixing is
complete, and lags on a sparse network.

![Share adopted over time against the Bass equation](images/gallery/bass_diffusion.png)

## Submit your model

The gallery is also open to community models built with Modelly that are not in the zoo.
Open a pull request that adds your model's entry to this page under a section
"Community models", with one PNG of at most 100 KB in `docs/images/gallery/community/`, and
fill in the template below in the pull request description. A gallery entry does not need
a validation test, but it must run from a seed and say how it was checked.

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

The maintainers run the command before merging. Models that are validated, small and of
general interest may be invited into the zoo.
