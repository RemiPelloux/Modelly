# Synthetic populations

`modelly.population` builds people, households, places and contact networks from aggregate tables. It needs numpy and pandas; `locate_households` takes a `GeoSpace` (the `geo` extra). The guide is [Synthetic populations](https://remipelloux.github.io/Modelly/dev/population.html).

Module

Contents

modelly.population.fitting

ipf, trs, synthesize_population, marginal_errors

modelly.population.annealing

anneal, Annealing, total_absolute_error

modelly.population.households

assign_households, household_sizes, HouseholdSpec

modelly.population.places

locate_households, assign_places, PlaceSpec

modelly.population.contacts

contact_network, place_groups, ContactLayers

## Fitting marginals

Synthetic populations from census-style marginals, by iterative proportional fitting.

Census tables usually give, per region, the count of people in each level of each attribute (age band, sex, household size) but not the joint table. `ipf` fits a joint table to those marginals, starting from a `seed` (a microsample cross-tabulation, or ones), `trs` rounds a fitted table to whole people (truncate, replicate, sample), and `synthesize_population` turns the fitted tables into one row per person, ready to create one agent per row. `marginal_errors` compares a synthetic population with the marginals it was drawn from.

**Reference:**

Lovelace, R. and Ballas, D. (2013). ‘Truncate, replicate, sample’: a method for creating integer weights for spatial microsimulation. Computers, Environment and Urban Systems, 41, 1-11.

#### `ipf(seed: ndarray, marginals: Sequence[Sequence[float]], tolerance: float = 1e-10, max_iterations: int = 1000) → ndarray`

Fit a table to its one-dimensional marginals by iterative proportional fitting.

**Parameters:**

- **seed** – the starting table, one axis per attribute; its zeros stay zero.
- **marginals** – the target totals along each axis, in axis order; all sum to the same total.
- **tolerance** – stop when no marginal is off by more than `tolerance` times the total.
- **max_iterations** – the most fitting rounds.

**Returns:**

the fitted table, of the shape of `seed`.

#### `synthesize_population(categories: Mapping[str, Sequence[Any]], marginals: Mapping[Any, Mapping[str, Sequence[float]]], rng: Generator, seed: ndarray | None = None) → DataFrame`

One row per synthetic person, with a `region` column and one column per attribute.

**Parameters:**

- **categories** – attribute name to its levels, for example `{"age": ["0-17", "18+"]}`.
- **marginals** – region label to, per attribute, the count of people at each level.
- **rng** – a numpy generator (`model.rng`) to round fitted counts to whole people.
- **seed** – the starting joint table (shape: one axis per attribute); defaults to ones.

**Returns:**

a DataFrame. The fitted table is rounded to whole people at random, one level of the first attribute at a time (floors, then the remainder drawn in proportion to the fractional parts). With whole-number marginals every region gets exactly its total and its first attribute’s counts; the other marginals are met in expectation, each count off by less than the number of first-attribute levels.

#### `trs(expected: ndarray, rng: Generator) → ndarray`

Whole counts with the same total: truncate, replicate, sample.

Every cell keeps the floor of its expected count; the people left over (the total’s rounding minus the floors) go to distinct cells drawn without replacement, in proportion to their fractional parts. Each count is then within one of its expected value and the total is exact for a whole-number total.

**Parameters:**

- **expected** – the fitted counts, any shape; they are flattened.
- **rng** – a numpy generator (`model.rng`).

**Returns:**

an `int64` array of the flattened shape.

#### `marginal_errors(people: DataFrame, marginals: Mapping[Any, Mapping[str, Sequence[float]]], categories: Mapping[str, Sequence[Any]]) → DataFrame`

Synthetic against target counts, one row per (region, attribute, level).

**Parameters:**

- **people** – one row per person, with a `region` column and one column per attribute.
- **marginals** – region label to, per attribute, the target count at each level.
- **categories** – attribute name to its levels, in the order of the marginals.

**Returns:**

a DataFrame with columns `region`, `attribute`, `level`, `target`, `synthetic` and `error` (`synthetic - target`).

## Combinatorial optimisation

Combinatorial optimisation: choose whole records from a sample to match census totals.

IPF fits a table of people; it cannot keep the members of a household together. The combinatorial-optimisation approach does: draw `size` records (households, each with its members’ counts) from a sample, with replacement, and swap one drawn record for another while that brings the totals closer to the targets. `anneal` does it by simulated annealing: a swap that worsens the total absolute error `TAE` by `d` is still taken with probability `exp(-d / T)`, where the temperature `T` falls geometrically, so the search can leave local optima early and settles at the end.

The sample is yours: a public-use microdata sample, a survey, or a synthetic sample. Modelly bundles no microdata.

References

Williamson, P., Birkin, M. and Rees, P. H. (1998). The estimation of population microdata by using data from small area statistics and samples of anonymised records. Environment and Planning A, 30(5), 785-816.

Harland, K., Heppenstall, A., Smith, D. and Birkin, M. (2012). Creating realistic synthetic populations at varying spatial scales: a comparative critique of population synthesis techniques. Journal of Artificial Societies and Social Simulation, 15(1), 1.

#### `class Annealing(size: int, iterations: int = 20000, temperature: float = 1.0, cooling: float = 0.9995)`

One simulated-annealing run: how many records to draw and the cooling schedule.

**Variables:**

- **size** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the number of records to draw (the region’s households, say).
- **iterations** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the most swaps tried; the run stops early at a perfect fit.
- **temperature** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the starting temperature, in units of the targets (people).
- **cooling** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the factor applied to the temperature after every swap tried.

#### `total_absolute_error(sample: DataFrame, selection: ndarray, targets: Mapping[str, float]) → float`

`sum(|total of the selected records - target|)` over the target columns.

**Parameters:**

- **sample** – one row per record, with one numeric column per target.
- **selection** – row positions of the selected records (repeats allowed).
- **targets** – column name to its target total.

#### `anneal(sample: DataFrame, targets: Mapping[str, float], settings: Annealing, rng: Generator) → ndarray`

Row positions of `settings.size` records of `sample` whose totals fit `targets`.

**Parameters:**

- **sample** – one row per record, with one numeric column per target (for a household: its children, adults, seniors, a one-hot of its size, …).
- **targets** – column name to its target total in the region.
- **settings** – the number of records and the cooling schedule.
- **rng** – a numpy generator (`model.rng`): the start and every swap.

**Returns:**

an `intp` array of `settings.size` row positions, with repeats.

## Households

Households: synthetic people grouped by a household-size distribution, each with a head.

Census tables give, per region, how many households have one, two, three… members. `assign_households` draws that many households for the people of each region (rounded to whole households with `trs`, then grown or shrunk one member at a time until they hold exactly the region’s people), gives every household a head among the people who can head one (adults), and spreads everybody else over the remaining places at random. The people, and so their marginals, are unchanged: only a `household` column is added.

#### `class HouseholdSpec(sizes: Mapping[Any, Sequence[float]], heads: Sequence[Any], column: str = 'age')`

How to group the people of each region into households.

**Variables:**

- **sizes** ([*collections.abc.Mapping*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)*[**Any**, *[*collections.abc.Sequence*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)*[*[*float*](https://docs.python.org/3/builtins/functions.html#float)*]**]*) – region label to the shares (or counts) of households with 1, 2, …, k members; only the proportions matter.
- **heads** ([*collections.abc.Sequence*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)*[**Any**]*) – the levels of `column` whose people can head a household (adults).
- **column** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the attribute `heads` refers to.

#### `household_sizes(people: int, shares: Sequence[float], rng: Generator) → ndarray`

Sizes of households that hold exactly `people` people, in random order.

**Parameters:**

- **people** – the number of people to house.
- **shares** – the shares (or counts) of households with 1, 2, …, k members.
- **rng** – a numpy generator (`model.rng`).

**Returns:**

an `int64` array of household sizes between 1 and k that sums to `people`.

#### `assign_households(people: DataFrame, spec: HouseholdSpec, rng: Generator) → DataFrame`

A copy of `people` with a `household` column: ids unique across regions.

**Parameters:**

- **people** – one row per person, with a `region` column and `spec.column`.
- **spec** – the household sizes per region and who can head a household.
- **rng** – a numpy generator (`model.rng`).

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – if a region has more households than people who can head one.

## Homes and places

Homes, schools and workplaces: where synthetic people live, study and work.

`locate_households` puts every household at one random point of its region (all its members share it). `assign_places` then sends the people who attend a kind of place (pupils to schools, workers to workplaces) to the nearest place that still has room, in random order, never farther than a maximum distance: people with no place within reach get `-1`. Distances are straight lines in the coordinates’ units (metres in a projected CRS such as a `GeoSpace`’s).

#### `class PlaceSpec(name: str, members: Sequence[Any], column: str = 'age', max_distance: float = inf)`

Who attends a kind of place, and how far they may travel to it.

**Variables:**

- **name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the column of people that receives the place (`"school"`, `"work"`).
- **members** ([*collections.abc.Sequence*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)*[**Any**]*) – the levels of `column` whose people attend.
- **column** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the attribute `members` refers to.
- **max_distance** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – nobody is sent farther than this; unlimited by default.

#### `locate_households(people: DataFrame, space: Any, rng: Generator) → DataFrame`

A copy of `people` with `x` and `y`: one random point per household.

**Parameters:**

- **people** – one row per person, with `region` and `household` columns.
- **space** – a `GeoSpace` whose regions are the people’s regions (anything with `random_points(region, n, rng)` returning an `(n, 2)` array).
- **rng** – a numpy generator (`model.rng`).

#### `assign_places(people: DataFrame, places: DataFrame, spec: PlaceSpec, rng: Generator) → DataFrame`

A copy of `people` with a `spec.name` column: the row of `places`, or `-1`.

**Parameters:**

- **people** – one row per person, with `x`, `y` and `spec.column`.
- **places** – one row per place, with `x`, `y` and `capacity` (people it takes).
- **spec** – who attends and how far they may go.
- **rng** – a numpy generator (`model.rng`): the order in which people choose.

**Returns:**

the copy; a person’s place is `places.iloc[place]`. Everybody else gets `-1`.

## Contact networks

Contact networks from places: who meets whom at home, at school and at work.

`contact_network` links the people who share a place on one layer per kind of place, in a `MultilayerNetwork` (`modelly.space.networks`): everybody in a household knows everybody else in it; pupils of a school are split at random into classes, and workers of a workplace into teams, each a clique. Node `i` is the `i`-th row of `people`, so `contact_matrix(network, groups)` gives the mean contacts between age groups for an age-structured model, and `network.adjacency() @ infected` drives a network epidemic.

#### `class ContactLayers(weights: Mapping[str, float]=<factory>, group_sizes: Mapping[str, int]=<factory>)`

The layers of a contact network and the size of the cliques on each.

**Variables:**

- **weights** ([*collections.abc.Mapping*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*float*](https://docs.python.org/3/builtins/functions.html#float)*]*) – layer name to its weight; each name is a column of people holding the place (household, school, workplace) of every person, `-1` for none.
- **group_sizes** ([*collections.abc.Mapping*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*int*](https://docs.python.org/3/builtins/functions.html#int)*]*) – layer name to the people per clique within one place (a class, a team); a layer not listed links everybody who shares a place.

#### `contact_network(people: DataFrame, rng: Generator, layers: ContactLayers | None = None) → MultilayerNetwork`

A `MultilayerNetwork` over the rows of `people`, one layer per kind of place.

**Parameters:**

- **people** – one row per person, with one column per layer (see `ContactLayers`).
- **rng** – a numpy generator (`model.rng`) to split places into classes and teams.
- **layers** – the layers, their weights and clique sizes; household (1.0), school (0.5, classes of 25) and work (0.25, teams of 10) by default.

#### `place_groups(places: ndarray, size: int | None, rng: Generator) → list[ndarray]`

The rows that share each place, in place order, split at random into `size` groups.

**Parameters:**

- **places** – the place of every row; `-1` (no place) is left out.
- **size** – people per group within a place; `None` keeps each place whole.
- **rng** – a numpy generator, used only when `size` is given.
