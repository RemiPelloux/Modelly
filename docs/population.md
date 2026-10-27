# Synthetic populations

`modelly.population` builds a starting population from aggregate tables: people with their
attributes, grouped into households, living at points of their region, going to schools and
workplaces, and linked by a contact network. Every step adds columns to one pandas DataFrame
with one row per person, so the result creates one agent per row, fills the columns of a
column-backed agent set, or summarises into the inputs of a cohort model.

The toolkit needs only numpy and pandas. `locate_households` takes a `GeoSpace`, which needs the
`geo` extra (`pip install "modelly-abm[geo]"`); everything else works on plain coordinates.

| Step | Call | Adds |
|---|---|---|
| People from marginal tables | `synthesize_population` (IPF, then `trs` rounding) | `region` and one column per attribute |
| Or whole records from a sample | `anneal` (simulated annealing) | the rows of the sample to copy |
| Check the fit | `marginal_errors` | a table of target and synthetic counts |
| Households | `assign_households` | `household` |
| Homes | `locate_households` | `x`, `y` |
| Schools and workplaces | `assign_places` | `school`, `work` (or any name) |
| Contacts | `contact_network` | a `MultilayerNetwork` |

## People from census marginals

Census tables give, per region, the number of people at each level of each attribute (age
band, sex, household size) but not the joint table. `ipf(seed, marginals)` fits a joint table to
the marginals by iterative proportional fitting; its seed can be a cross-tabulation of a
microsample, so the fit keeps the sample's associations (and its zeros). `trs` turns the
fitted table into whole people: it keeps the floor of every cell and draws the people left over
in proportion to the fractional parts (truncate, replicate, sample; Lovelace and Ballas 2013).
`synthesize_population` does both, region by region:

```python
import numpy as np

from modelly import Model
from modelly.population import marginal_errors, synthesize_population

categories = {"age": ["0-17", "18-64", "65+"], "sex": ["f", "m"]}
marginals = {
    "T01": {"age": [210, 600, 190], "sex": [508, 492]},
    "T02": {"age": [90, 330, 80], "sex": [251, 249]},
}
model = Model(rng=42)
people = synthesize_population(categories, marginals, model.rng)
errors = marginal_errors(people, marginals, categories)
```

Every region gets exactly its total and its first attribute's counts. The other marginals are
met to within the rounding: each count is off by less than the number of levels of the first
attribute, and `marginal_errors` shows by how much. The people are drawn from `model.rng`, so a
seed gives the same population.

`modelly.space.geo.ipf` and `modelly.space.geo.synthesize_population` are the same functions and
keep working.

## Whole households by combinatorial optimisation

IPF fits a table of people; it cannot keep the members of a household together. The
combinatorial-optimisation approach (Williamson, Birkin and Rees 1998) does: choose as many
records as the region has households from a sample of household records, with replacement, so
that their totals match the region's tables. `anneal` searches by simulated annealing: it swaps
one chosen record for another, keeps every swap that lowers the total absolute error, and keeps
a swap that raises it by `d` with probability `exp(-d / T)`, the temperature `T` falling at
every swap.

```python
import pandas as pd

from modelly.population import Annealing, anneal, total_absolute_error

# One row per sample household: its members per age band and a one-hot of its size.
sample = pd.read_csv("household_sample.csv")
targets = {"children": 210, "adults": 600, "seniors": 190, "size_1": 120, "size_2": 140}
chosen = anneal(sample, targets, Annealing(size=430), model.rng)
total_absolute_error(sample, chosen, targets)
households = sample.iloc[chosen].reset_index(drop=True)
```

`Annealing` also sets the number of swaps tried (`iterations`, default 20,000), the starting
temperature (in people) and the cooling factor per swap. The sample is yours: a public-use
microdata sample, a survey, or a sample you make up. Modelly ships none.

## Households

`assign_households` groups the people of each region into households of the sizes in a
household-size table. It rounds the table to whole households with `trs`, grows or shrinks
random households one member at a time until they hold exactly the region's people, gives every
household a head among the people who can head one, and spreads the others over the remaining
places at random. The people, and so the marginals, do not change.

```python
from modelly.population import HouseholdSpec, assign_households

sizes = [0.28, 0.34, 0.16, 0.14, 0.08]  # shares of households of 1 to 5 people
spec = HouseholdSpec({"T01": sizes, "T02": sizes}, heads=["18-64", "65+"])
people = assign_households(people, spec, model.rng)
```

A region that needs more heads than it has adults is an error, not a silent fix.

## Homes, schools and workplaces

`locate_households` puts each household at a random point of its region; all its members share
it. `assign_places` then sends the people who attend a kind of place to the nearest place with
room, in random order, never farther than `max_distance` (in the coordinates' units, metres for
a `GeoSpace`). People with no place within reach get `-1`. The places are a DataFrame with `x`,
`y` and `capacity`; a person's place is `places.iloc[person.school]`.

```python
import pandas as pd

from modelly.population import PlaceSpec, assign_places, locate_households
from modelly.space.geo import GeoSpace

space = GeoSpace(tracts, random=model.random)  # tracts indexed like the marginals
people = locate_households(people, space, model.rng)
centres = tracts.to_crs(space.crs).geometry.centroid
schools = pd.DataFrame({"x": centres.x, "y": centres.y, "capacity": 600})
people = assign_places(
    people, schools, PlaceSpec("school", ["0-17"], max_distance=10_000), model.rng
)
people = assign_places(people, workplaces, PlaceSpec("work", ["18-64"]), model.rng)
```

## Contact networks

`contact_network` links the people who share a place, one layer per kind of place, in a
`MultilayerNetwork` (see [Networks](networks.md)): everybody in a household knows everybody else
in it; the pupils of a school are split at random into classes and the workers of a workplace
into teams, each a clique. Node `i` is row `i` of `people`. The default layers are household
(weight 1), school (0.5, classes of 25) and work (0.25, teams of 10); `ContactLayers` changes
them.

```python
from modelly.population import ContactLayers, contact_network
from modelly.space.networks import contact_matrix

network = contact_network(people, model.rng)
groups = pd.Categorical(people.age, categories=categories["age"]).codes
contacts = contact_matrix(network, groups)  # mean contacts between age groups
pressure = network.adjacency() @ infected  # for a network epidemic
```

The [layered epidemic example](https://github.com/RemiPelloux/Modelly/tree/main/modelly/examples/spatial/layered_epidemic)
runs an epidemic on a network of the same three layers.

## Starting the age-structured SEIR model

The [age-structured SEIR](zoo/age_seir.md) zoo model runs on a synthetic population through
`scenario_from_population`, which counts the age groups and measures the contact matrix on the
network. Its default scenario does not change.

```python
from modelly.zoo.age_seir.model import AgeSEIR, scenario_from_population

scenario = scenario_from_population(people, network, ("0-17", "18-64", "65+"), rng=5)
seir = AgeSEIR(scenario)
seir.run()
seir.attack_rate(), seir.final_size()
```

`tests/population/test_sample_region.py` builds a population of about 20,000 people for the 41
census tracts of Chittenden County, Vermont (the bundled boundaries, see
[Geospatial models](geospatial.md#real-data-samples)) from illustrative tables, checks that it
reproduces every marginal within the rounding tolerance, that households, schools and workplaces
respect their sizes, capacities and distances, and that the SEIR model started from it follows
its final-size relation.

## Privacy

Everything here works from aggregate tables, and the people it makes are synthetic: no row is a
real person, and Modelly bundles no personal data and no microdata. The marginals in the tests
and on this page are made up. Aggregates of very small areas can still disclose people: use
published, disclosure-controlled tables, keep any microdata sample under the terms it was
released with, and do not publish a synthetic population fitted to unpublished small counts.

## References

- Lovelace, R. and Ballas, D. (2013). 'Truncate, replicate, sample': a method for creating
  integer weights for spatial microsimulation. *Computers, Environment and Urban Systems*, 41,
  1-11.
- Williamson, P., Birkin, M. and Rees, P. H. (1998). The estimation of population microdata by
  using data from small area statistics and samples of anonymised records. *Environment and
  Planning A*, 30(5), 785-816.
- Harland, K., Heppenstall, A., Smith, D. and Birkin, M. (2012). Creating realistic synthetic
  populations at varying spatial scales: a comparative critique of population synthesis
  techniques. *Journal of Artificial Societies and Social Simulation*, 15(1), 1.

The [API reference](apis/population.md) lists every function.
