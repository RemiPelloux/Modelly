# Model zoo

`modelly.zoo` is the catalogue of reference models; the guide is [Model zoo](https://remipelloux.github.io/Modelly/dev/zoo/index.html). Each model is in `modelly.zoo.<name>.model`.

## Catalogue and copying

The catalogue of zoo models: one `ZooModel` per reference model.

Each model lives in `modelly/zoo/<name>/model.py`, a single module that imports only public `modelly` modules, so `copy_model` can write it into a new project unchanged. The module docstring describes the model, its validation and its references.

#### `class ZooModel(name: str, title: str, field: str, model: str, scenario: str, summary: str, validation: str)`

One reference model of the zoo.

**Variables:**

- **name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the zoo name (`modelly zoo info <name>`), also its package name.
- **title** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – a human-readable title.
- **field** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the scientific field.
- **model** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the `Model` subclass, by name, in `modelly.zoo.<name>.model`.
- **scenario** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – its `Scenario` subclass, by name.
- **summary** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – one sentence.
- **validation** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – what the validation test checks.

#### `property module: str`

The dotted name of the model’s module.

#### `property source: Path`

The path of the model’s source file.

#### `property card: Path`

The path of the model’s card, `card.toml` next to its module.

#### `load() → tuple[type, type]`

Import the module and return `(model class, scenario class)`.

#### `doc() → str`

The model module’s docstring: the description and the references.

#### `names() → list[str]`

The zoo names, in catalogue order.

#### `get(name: str) → ZooModel`

The zoo model called `name`.

**Raises:**

[**KeyError**](https://docs.python.org/3/builtins/exceptions.html#KeyError) – if there is none; the message suggests the closest names.

Copy a zoo model into a folder of its own, to start a project from it.

#### `parameters(entry: ZooModel) → dict[str, object]`

The scenario’s parameters and their default values.

#### `readme(entry: ZooModel) → str`

The README written next to a copied model.

#### `copy_model(name: str, directory: str | Path) → list[Path]`

Write zoo model `name` into `directory` as `model.py` and `README.md`.

The folder is created if needed. Nothing is overwritten.

Example

```default
>>> import tempfile
>>> folder = Path(tempfile.mkdtemp()) / "my_epidemic"
>>> [path.name for path in copy_model("age_seir", folder)]
['model.py', 'README.md']
```

**Raises:**

- [**KeyError**](https://docs.python.org/3/builtins/exceptions.html#KeyError) – if there is no zoo model `name`.
- [**FileExistsError**](https://docs.python.org/3/builtins/exceptions.html#FileExistsError) – if `model.py` or `README.md` already exists there.

Summary statistics shared by the zoo models and their validation tests.

#### `gini(values: ndarray) → float`

The Gini coefficient of non-negative `values`: 0 equality, near 1 one holds all.

Computed from the sorted values, `G = sum_i (2 i - n - 1) x_(i) / (n sum x)`.

Example

```default
>>> gini(np.array([1, 1, 1, 1]))
0.0
>>> gini(np.array([0, 0, 0, 4]))
0.75
```

#### `clusters(values: ndarray, gap: float, min_share: float = 0.0) → int`

The number of groups of 1-D `values` separated by more than `gap`.

Groups with fewer than `min_share` of the values (isolated extremists) are not counted.

Example

```default
>>> clusters(np.array([0.1, 0.11, 0.5, 0.52, 0.9]), gap=0.05)
3
>>> clusters(np.array([0.1, 0.11, 0.5, 0.52, 0.9]), gap=0.05, min_share=0.3)
2
```

## Epidemiology

Age-structured SEIR epidemic with a contact matrix.

A population split into age groups, each person susceptible (S), exposed (E), infectious (I) or recovered (R). A susceptible of group `a` is infected in one step with probability `1 - exp(-beta * sum_b C[a, b] * I_b / N_b)`, where `C[a, b]` is the mean number of contacts a member of `a` has with members of `b` per step (a contact matrix, as measured by social-contact surveys or computed by `modelly.space.networks.contact_matrix`). Exposed people become infectious with probability `incubation` per step and infectious people recover with probability `recovery` per step.

Everybody in the same group and state faces the same probabilities, so the population is a `CohortTable` with one row per (group, state): every transition is one binomial draw per row, with exactly the law of the per-person draws (see `docs/vectorised_phases.md`). A million people cost the same as a hundred.

Validation: the final-size relation. Summing the force of infection over the epidemic, `log(s_a) = log(s0_a) - (beta / recovery) * sum_b C[a, b] * (1 - s_b)`, where `s_a` is the share of group `a` never infected; with one group this is the Kermack-McKendrick relation `s = s0 * exp(-R0 * (1 - s))`. `final_size()` solves it and the test compares it with the simulated epidemic. `r0()` is `beta / recovery` times the spectral radius of the next-generation matrix. People vaccinated at the start (`vaccinated`) are immune: the relation holds with their share `v_a` removed, `log(s_a) = log(s0_a) - (beta / recovery) * sum_b C[a, b] * (1 - v_b - s_b)`.

Starting from a synthetic population: `scenario_from_population(people, network, levels)` takes the group sizes from the people’s age levels and the contact matrix from their contact network (`modelly.population`: households, schools and workplaces), so the model runs on a population built from census tables instead of the illustrative default.

References

Kermack, W. O. and McKendrick, A. G. (1927). A contribution to the mathematical theory of epidemics. Proceedings of the Royal Society A, 115, 700-721.

Mossong, J. et al. (2008). Social contacts and mixing patterns relevant to the spread of infectious diseases. PLoS Medicine, 5(3), e74.

Andersson, H. and Britton, T. (2000). Stochastic Epidemic Models and Their Statistical Analysis. Lecture Notes in Statistics 151, Springer.

#### `class State(*values)`

Infection states.

#### `class SEIRScenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

Parameters of the age-structured SEIR model.

The default contact matrix is illustrative (children, adults, seniors), not survey data; it is reciprocal, `N[a] * C[a, b] == N[b] * C[b, a]`.

**Variables:**

- **group_sizes** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)) – number of people in each age group.
- **contacts** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)) – contact matrix `C[a][b]`, contacts per step of a member of `a` with members of `b`.
- **beta** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – probability of transmission per contact with an infectious person.
- **incubation** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – probability per step that an exposed person becomes infectious.
- **recovery** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – probability per step that an infectious person recovers.
- **initial_infected** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)) – infectious people at the start, per group.
- **vaccinated** ([*tuple*](https://docs.python.org/3/builtins/stdtypes.html#tuple)) – people immune from the start (vaccinated), per group; empty for none.
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – default run length used by `run`.

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `class AgeSEIR(scenario: SEIRScenario = <class 'modelly.zoo.age_seir.model.SEIRScenario'>)`

SEIR over age groups, one cohort row per (group, state).

Example

```default
>>> model = AgeSEIR(SEIRScenario(rng=1, steps=50))
>>> model.run()
>>> int(model.counts().sum()) == sum(model.scenario.group_sizes)
True
```

Seed the infectious people; everybody else is susceptible.

#### `counts() → ndarray`

People per (group, state), shape `(n_groups, 4)`.

#### `force() → ndarray`

Per-step hazard of infection of a susceptible in each group.

#### `step() → None`

Recover, then progress, then infect, all from the start-of-step state.

#### `run(steps: int | None = None) → None`

Run `steps` steps (the scenario’s `steps` by default).

#### `r0() → float`

Basic reproduction number: spectral radius of the next-generation matrix.

#### `final_size(tolerance: float = 1e-12) → ndarray`

Share of each group ever infected, from the final-size relation.

#### `attack_rate() → ndarray`

Share of each group ever infected so far (the vaccinated were not).

#### `scenario_from_population(people: Any, network: Any, levels: Sequence, **parameters: Any) → SEIRScenario`

A scenario whose age groups and contacts come from a synthetic population.

**Parameters:**

- **people** – one row per person with an `age` column, as `modelly.population` builds it (`synthesize_population`, then `assign_households` and so on).
- **network** – the people’s contact network, node `i` the `i`-th row (`modelly.population.contact_network`); its weights are contacts per step.
- **levels** – the age levels in group order, for example `("0-17", "18-64", "65+")`.
- ****parameters** – any other `SEIRScenario` field (`rng`, `beta`, …); `initial_infected` defaults to 10 per group, or the whole group if smaller.

**Returns:**

an `SEIRScenario` with `group_sizes` counted from `people` and `contacts` from `contact_matrix(network, groups)`.

**Raises:**

[**ValueError**](https://docs.python.org/3/builtins/exceptions.html#ValueError) – if an age level has nobody in it.

#### `count_in(model: AgeSEIR, state: State) → int`

The number of people in `state`, all groups together (a model reporter).

Vector-borne transmission on a landscape (Ross-Macdonald).

Hosts live on the cells of a landscape grid and move to a random neighbouring cell with probability `move` per step; each is susceptible, infectious or recovered. Mosquitoes live in the cells too, `m` per host on average (times a per-cell `habitat` suitability, a raster of values), each susceptible, exposed (the extrinsic incubation) or infectious. Every step a mosquito survives with probability `survival` and bites `a` times, each time a host of its cell chosen at random. A bite of an infectious mosquito infects a susceptible host with probability `b`; a bite on an infectious host infects a susceptible mosquito with probability `c`. Exposed mosquitoes become infectious with probability `incubation` per step, infectious hosts recover with probability `recovery`, and new susceptible mosquitoes emerge so as to keep the density at `m`.

Mosquitoes in the same cell and state are interchangeable, so they are a `CohortTable` with one row per (cell, state): survival, infection and incubation are binomial draws per row. Hosts are agents with `Column` arrays for their state and cell row.

Validation: the Ross-Macdonald reproduction number (host to host, over one full cycle), `R0 = m a^2 b c P / (recovery (1 - survival))`, where `P` is the probability that an infected mosquito survives the incubation, is linear in the vector density `m` (`r0()`). Outbreaks are small when `R0 < 1` and their size grows with `R0` above it, so the attack rates of three densities come out in the order of their `R0`.

References

Ross, R. (1911). The Prevention of Malaria, 2nd ed. John Murray.

Macdonald, G. (1957). The Epidemiology and Control of Malaria. Oxford University Press.

#### `class Host(*values)`

Host states.

#### `class Vector(*values)`

Mosquito states.

#### `class Person(model: M, *args, **kwargs)`

A host: its infection state and the row of its cell.

Create a new agent.

**Parameters:**

- **model** ([*Model*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.model.Model)) – The model instance in which the agent exists.
- **args** – Passed on to super.
- **kwargs** – Passed on to super.

Notes

to make proper use of python’s super, in each class remove the arguments and keyword arguments you need and pass on the rest to super

#### `property state`

Column(int8, default=0)

#### `property row`

Column(int64, default=0)

#### `class VectorScenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

Parameters of the vector-borne model (one step is one day).

**Variables:**

- **width** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – landscape cells from west to east.
- **height** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – landscape cells from south to north.
- **hosts_per_cell** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – hosts placed in every cell at the start.
- **habitat** ([*object*](https://docs.python.org/3/builtins/functions.html#object)) – optional per-cell suitability, shape `(width, height)`, scaling the vector density (a raster’s values); uniform when `None`.
- **m** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – mosquitoes per host.
- **a** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – bites per mosquito per day.
- **b** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – probability that an infectious bite infects a susceptible host.
- **c** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – probability that a bite on an infectious host infects a mosquito.
- **survival** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – daily survival probability of a mosquito.
- **incubation** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – daily probability that an exposed mosquito becomes infectious.
- **recovery** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – daily probability that an infectious host recovers.
- **move** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – daily probability that a host moves to a neighbouring cell.
- **initial_infected** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – infectious hosts at the start.
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – default run length used by `run`.

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `class VectorBorne(scenario: VectorScenario = <class 'modelly.zoo.vector_borne.model.VectorScenario'>)`

Ross-Macdonald transmission between moving hosts and mosquito cohorts per cell.

Example

```default
>>> model = VectorBorne(VectorScenario(rng=1, steps=30))
>>> model.run()
>>> 0.0 <= model.attack_rate() <= 1.0
True
```

Place the hosts, infect a few, and fill every cell with mosquitoes.

#### `pressures() → tuple[ndarray, ndarray]`

Daily infection hazard per cell: on a susceptible host, on a susceptible mosquito.

#### `step() → None`

Bites from the start-of-day state, then the mosquito life cycle, then moves.

#### `mosquito_day(on_vector: ndarray) → None`

Survive, incubate, get infected, emerge.

#### `run(steps: int | None = None) → None`

Run `steps` days (the scenario’s by default), or until the infection is gone.

#### `infected() → bool`

Whether any host is infectious or any mosquito exposed or infectious.

#### `r0() → float`

Ross-Macdonald R0 (host to host) for this scenario’s uniform vector density.

#### `attack_rate() → float`

Share of hosts ever infected.

#### `susceptible(model: VectorBorne) → int`

Susceptible hosts (a model reporter).

#### `infectious(model: VectorBorne) → int`

Infectious hosts (a model reporter).

#### `recovered(model: VectorBorne) → int`

Recovered hosts (a model reporter).

An epidemic among agents coupled to a hospital-capacity model.

People are agents, each susceptible (S), infectious (I) or recovered (R), mixing homogeneously. A susceptible is infected in a step with probability `1 - exp(-beta_eff * I / N)`, an infectious person recovers with probability `recovery` per step, and a share `severe` of the new infections need a hospital bed.

The hospital is a stock-flow model (`modelly.couple.StockFlow`) integrated with `solve_ivp`: the `occupied` beds fill with the admissions of the agents’ step and empty at rate `occupied / stay`; the `beds` open and close towards `base_beds + surge * occupied` with time constant `ramp`, as a hospital adds surge capacity. People respond to the hospital’s pressure: contacts fall with the share of beds occupied, `beta_eff = beta / (1 + response * occupied / beds)`. The agents’ phase reads `occupied` and `beds` and writes `admissions`; the hospital, one phase later, reads the admissions and writes the beds, so the feedback acts with a lag of one step.

Validation: three known answers. Without the response (`response = 0`) the epidemic is the stochastic general epidemic, whose attack rate solves the final-size relation `s = s0 exp(-R0 (1 - s))` with `R0 = beta / recovery`, within the central-limit bound (Andersson and Britton, 2000). The hospital equations are linear, so for the admissions of each step, held over the step, the exact solution is a matrix exponential; the integrated occupancy and beds match it to the solver’s tolerance. And the stock-flow keeps its mass balance: the admissions the agents wrote equal the patients in hospital plus those discharged, to round-off.

References

Kermack, W. O. and McKendrick, A. G. (1927). A contribution to the mathematical theory of epidemics. Proceedings of the Royal Society A, 115, 700-721.

Andersson, H. and Britton, T. (2000). Stochastic Epidemic Models and Their Statistical Analysis. Lecture Notes in Statistics 151, Springer.

Sterman, J. D. (2000). Business Dynamics: Systems Thinking and Modeling for a Complex World. Irwin/McGraw-Hill.

#### `class State(*values)`

Infection states.

#### `class Person(model: HospitalEpidemic, state: int)`

A person: their infection state.

Start in `state`.

#### `property state`

Column(int8, default=0)

#### `class HospitalScenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

Parameters of the epidemic and of the hospital.

**Variables:**

- **population** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – number of people.
- **initial_infected** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – infectious people at the start.
- **beta** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – transmission rate per step (`R0 = beta / recovery`).
- **recovery** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – probability per step that an infectious person recovers.
- **severe** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – share of new infections admitted to hospital.
- **stay** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – mean length of a hospital stay, in steps.
- **base_beds** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – beds open when the hospital is empty.
- **surge** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – beds opened per occupied bed.
- **ramp** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – time constant of opening and closing beds, in steps.
- **response** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – how strongly contacts fall with the share of beds occupied.
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – default run length used by `run`.

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `class HospitalEpidemic(scenario: HospitalScenario = <class 'modelly.zoo.hospital_epidemic.model.HospitalScenario'>)`

SIR agents whose admissions drive a hospital stock-flow model, and back.

**Variables:**

- **hospital** – the hospital `StockFlow` (stocks `occupied` and `beds`).
- **coupling** – the schedule: the agents in phase 0, the hospital in phase 1.
- **admitted** – admissions written by the agents so far.

Example

```default
>>> model = HospitalEpidemic(HospitalScenario(rng=1, steps=30))
>>> model.run()
>>> model.hospital.state["beds"] > 0
True
```

Make the people, the hospital and the coupling between them.

#### `transmit() → None`

Recover, then infect from the start-of-step state; write the admissions.

#### `step() → None`

One step of the agents, then one step of the hospital.

#### `run(steps: int | None = None) → None`

Run `steps` steps (the scenario’s `steps` by default).

#### `counts() → ndarray`

People in each state, `[S, I, R]`.

#### `r0() → float`

The basic reproduction number `beta / recovery`.

#### `final_size(tolerance: float = 1e-12) → float`

Share ever infected without the response, from the final-size relation.

#### `attack_rate() → float`

Share of the population ever infected so far.

#### `hospital(s: HospitalScenario) → StockFlow`

The hospital: admissions fill `occupied`, beds follow the occupancy.

#### `admission_rate(stocks: dict[str, float], inputs: dict[str, float]) → float`

The admissions of the agents’ step, spread over the step (one unit of time).

#### `discharge_rate(stocks: dict[str, float], inputs: dict[str, float], scenario: HospitalScenario) → float`

Patients leave at rate `occupied / stay`.

#### `opening_rate(stocks: dict[str, float], inputs: dict[str, float], scenario: HospitalScenario) → float`

Beds open (or close, when negative) towards `base_beds + surge * occupied`.

#### `count_in(model: HospitalEpidemic, state: State) → int`

The number of people in `state` (a model reporter).

#### `quantity(model: HospitalEpidemic, name: str, default: float | None = None) → float`

A coupling quantity (a model reporter); `default` before it is first written.

## Ecology

Individual-based population with energy budgets.

Foragers walk a grid on which a resource flows in at a constant rate per cell. Every step each forager moves to a random neighbouring cell, the foragers in a cell share its resource equally and turn it into energy with an assimilation `efficiency`, and each pays a metabolic `cost`. A forager whose energy reaches `birth_threshold` splits it with an offspring in its cell; one whose energy falls below zero starves.

Validation: the energy balance. Energy is the only currency, so it regulates the population. The resource is never capped and is eaten whenever a forager visits, so in the long run all of it is eaten: intake equals inflow. At equilibrium the energy assimilated equals the energy spent, `efficiency * inflow * cells = cost * N`, which gives the carrying capacity `K = efficiency * inflow * cells / cost` (`carrying_capacity()`). The only energy leaving the balance otherwise is the deficit of starving foragers, at most one `cost` each, so the mean population sits at or slightly above `K`.

The foragers keep their energy and their cell row in `Column` arrays and are placed by row (`CellIndex.track`): moving, eating and starving are whole-population numpy operations; only births create objects.

**Reference:**

Grimm, V. and Railsback, S. F. (2005). Individual-based Modeling and Ecology. Princeton University Press.

#### `class Forager(model: EnergyBudget, row: int, energy: float)`

A forager: its energy and the row of the cell it stands on.

Place the forager in cell `row` with `energy`.

#### `property row`

Column(int64, default=0)

#### `property energy`

Column(float64, default=0)

#### `reproduce() → None`

Split the energy with an offspring in the same cell.

#### `class EnergyScenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

Parameters of the energy-budget population.

**Variables:**

- **width** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – grid cells from west to east.
- **height** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – grid cells from south to north.
- **initial** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – foragers at the start, on random cells.
- **initial_energy** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – energy of each initial forager.
- **inflow** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – resource added to every cell per step.
- **efficiency** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – share of the eaten resource turned into energy.
- **cost** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – energy spent by a forager per step.
- **birth_threshold** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – energy at which a forager splits with an offspring.
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – default run length used by `run`.

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `class EnergyBudget(scenario: EnergyScenario = <class 'modelly.zoo.energy_budget.model.EnergyScenario'>)`

Foragers that eat, pay a metabolic cost, reproduce and starve on a resource grid.

Example

```default
>>> model = EnergyBudget(EnergyScenario(rng=1, steps=50))
>>> model.run()
>>> model.population() > 0
True
```

Make the grid and scatter the initial foragers.

#### `step() → None`

Move, eat, pay the cost, starve, reproduce.

#### `run(steps: int | None = None) → None`

Run `steps` steps (the scenario’s `steps` by default).

#### `population() → int`

The number of live foragers.

#### `carrying_capacity() → float`

`K = efficiency * inflow * cells / cost`, from the energy balance.

#### `population(model: EnergyBudget) → int`

The number of foragers (a model reporter).

#### `stock(model: EnergyBudget) → float`

The uneaten resource on the grid (a model reporter).

Foragers on a diffusing nutrient field.

A nutrient enters a closed landscape along its western edge (a river bank, say) at `supply` per edge cell per step, diffuses with coefficient `diffusion` and decays at rate `decay`: a `modelly.couple.Field` on the grid’s `nutrient` layer, stepped on its own stable sub-steps. Foragers walk the grid at random. Every step each moves to a random neighbouring cell, the foragers in a cell share all of its nutrient and turn it into energy with an assimilation `efficiency`, and each pays a metabolic `cost`. A forager whose energy reaches `birth_threshold` splits it with an offspring; one whose energy falls below zero starves.

The two scales are coupled by a `Coupling`: the foragers’ phase reads the field and writes `nutrient_input` (the supply minus what was eaten, per cell), and the field, one phase later, adds that input and diffuses. Nothing else changes the field, so its budget closes exactly: the nutrient on the grid is the supply minus what was eaten and what decayed, to round-off.

Validation: the energy balance. At equilibrium the nutrient stock is stationary, so what the foragers eat equals what enters minus what decays, and what they assimilate equals what they spend: `efficiency * (supply_total - decayed) = cost * N`. Without decay this is the carrying capacity `K = efficiency * supply * height / cost` (`carrying_capacity()`) however far the nutrient has to diffuse; with decay the measured decay loss takes its share. The foragers’ density falls with the distance from the river, as the diffusing nutrient does.

References

Grimm, V. and Railsback, S. F. (2005). Individual-based Modeling and Ecology. Princeton University Press.

Okubo, A. and Levin, S. A. (2001). Diffusion and Ecological Problems: Modern Perspectives, 2nd ed. Springer.

#### `class Forager(model: NutrientForagers, row: int, energy: float)`

A forager: its energy and the row of the cell it stands on.

Place the forager in cell `row` with `energy`.

#### `property row`

Column(int64, default=0)

#### `property energy`

Column(float64, default=0)

#### `reproduce() → None`

Split the energy with an offspring in the same cell.

#### `class NutrientScenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

Parameters of the foragers and of the nutrient field.

**Variables:**

- **width** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – grid cells from west to east.
- **height** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – grid cells from south to north.
- **initial** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – foragers at the start, on random cells.
- **initial_energy** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – energy of each initial forager.
- **supply** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – nutrient entering each cell of the western edge per step.
- **diffusion** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – diffusion coefficient of the nutrient, in cells squared per step.
- **decay** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – decay rate of the nutrient per step.
- **appetite** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the most nutrient a forager eats in a step.
- **efficiency** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – share of the eaten nutrient turned into energy.
- **cost** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – energy spent by a forager per step.
- **birth_threshold** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – energy at which a forager splits with an offspring.
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – default run length used by `run`.

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `class NutrientForagers(scenario: NutrientScenario = <class 'modelly.zoo.nutrient_foragers.model.NutrientScenario'>)`

Foragers that eat from a diffusing nutrient field, coupled phase by phase.

**Variables:**

- **field** – the nutrient `Field` on the grid’s `nutrient` layer.
- **eaten** – nutrient eaten so far.
- **deficit** – energy below zero of the foragers that starved so far.

Example

```default
>>> model = NutrientForagers(NutrientScenario(rng=1, steps=50))
>>> model.run()
>>> model.population() > 0
True
```

Make the grid, the field, the coupling and the initial foragers.

#### `forage() → None`

Move, eat up to the appetite, pay the cost, starve, reproduce; write the input.

#### `step() → None`

Forage, then add the input to the field and diffuse it for one step.

#### `run(steps: int | None = None) → None`

Run `steps` steps (the scenario’s `steps` by default).

#### `population() → int`

The number of live foragers.

#### `carrying_capacity() → float`

`K = efficiency * supply * height / cost`, from the energy balance without decay.

#### `density_by_column() → ndarray`

Foragers per cell in each column of the grid, west to east.

#### `population(model: NutrientForagers) → int`

The number of foragers (a model reporter).

#### `stock(model: NutrientForagers) → float`

The nutrient on the grid (a model reporter).

#### `decayed(model: NutrientForagers) → float`

The nutrient lost to decay so far (a model reporter).

Forest fire and succession on a raster.

A raster of cells, each empty, a tree, burning or burnt. At the start every cell holds a tree with probability `density` (or with its own probability, from a `cover` raster such as the values of a `modelly.space.geo.RasterLayer`), and the trees of the west edge are set alight. Every step a tree next to a burning cell (von Neumann neighbourhood) catches fire and a burning cell burns out. With `growth > 0` empty and burnt cells grow a tree with that probability per step and with `lightning > 0` a tree is struck with that probability per step: the Drossel-Schwabl forest-fire model of succession and disturbance.

The state is one integer per cell, a property layer of the grid (`model.layer`, shaped like the grid); the spread is one sparse product per step, `CellIndex.neighbor_sum`, over the grid’s adjacency.

Validation: without growth and lightning the fire burns exactly the clusters of trees that touch the west edge, so the model is site percolation on the square lattice. The share of trees burnt jumps, and the fire starts to reach the east edge, at the percolation threshold `p_c = 0.592746` (Newman and Ziff 2000): it stays small below and covers most trees above.

References

Drossel, B. and Schwabl, F. (1992). Self-organized critical forest-fire model. Physical Review Letters, 69(11), 1629-1632.

Newman, M. E. J. and Ziff, R. M. (2000). Efficient Monte Carlo algorithm and high-precision results for percolation. Physical Review Letters, 85(19), 4104-4107.

Stauffer, D. and Aharony, A. (1994). Introduction to Percolation Theory, 2nd ed. Taylor and Francis.

#### `class Cover(*values)`

Cell states.

#### `class ForestScenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

Parameters of the forest-fire model.

**Variables:**

- **width** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – cells from west to east.
- **height** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – cells from south to north.
- **density** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – probability that a cell starts with a tree.
- **cover** ([*object*](https://docs.python.org/3/builtins/functions.html#object)) – optional per-cell tree probability, shape `(width, height)` (a raster’s values); replaces `density` when given.
- **growth** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – probability per step that an empty or burnt cell grows a tree.
- **lightning** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – probability per step that a tree is struck and catches fire.
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – default run length used by `run`.

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `class ForestFire(scenario: ForestScenario = <class 'modelly.zoo.forest_fire.model.ForestScenario'>)`

Fire spreading through a tree raster, with optional regrowth and lightning.

Example

```default
>>> model = ForestFire(ForestScenario(rng=1, width=30, height=30))
>>> model.run()
>>> 0.0 <= model.burnt_share() <= 1.0
True
```

Plant the trees and ignite the west edge.

#### `step() → None`

Spread, burn out, then (in succession mode) strike and regrow.

#### `run(steps: int | None = None) → None`

Run `steps` steps (the scenario’s by default), or until the fire is out.

#### `burnt_share() → float`

Share of the initial trees that have burnt or are burning.

#### `spans() → bool`

Whether the fire has reached the east edge.

#### `count_of(model: ForestFire, cover: Cover) → int`

The number of cells in state `cover` (a model reporter).

## Economics

Continuous double auction: a zero-intelligence limit order book.

Prices are integer ticks. The book keeps, for every tick, the number of resting buy orders (bids) and sell orders (asks) of one unit each. Order flow is random, as in the zero-intelligence model of Farmer, Patelli and Zovko: each event is, with probabilities in proportion to its rate,

- a market buy or sell (rate `market_rate / 2` each): it takes one unit at the best opposite price;
- a limit buy or sell (rate `limit_rate / 2` each): it rests at a price drawn uniformly `1 .. window` ticks away from the opposite best quote, on its own side of it (a buy below the best ask, a sell above the best bid), so it never crosses;
- a cancellation (rate `cancel_rate` per resting order): a uniformly random resting order leaves the book.

A side is never emptied: an event that would remove its last order becomes a limit order on that side. A step is `events` events; the mid price is recorded after each step.

Validation: the stylised fact of fat tails (Cont, 2001). The excess kurtosis of mid-price returns is positive, far above the `sqrt(24 / n)` standard error it would have if returns were normal. The spread is at least one tick at all times.

References

Farmer, J. D., Patelli, P. and Zovko, I. I. (2005). The predictive power of zero intelligence in financial markets. PNAS, 102(6), 2254-2259.

Cont, R. (2001). Empirical properties of asset returns: stylized facts and statistical issues. Quantitative Finance, 1, 223-236.

#### `class OrderBookScenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

Parameters of the zero-intelligence order book.

**Variables:**

- **ticks** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – number of price levels.
- **window** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – limit orders rest 1 .. window ticks from the opposite best quote.
- **market_rate** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – rate of market orders (both sides together).
- **limit_rate** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – rate of limit orders (both sides together).
- **cancel_rate** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – rate of cancellation per resting order.
- **initial_depth** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – orders per level in the `window` levels of each side at start.
- **events** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – order events per step.
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – default run length used by `run`.

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `class OrderBook(scenario: OrderBookScenario = <class 'modelly.zoo.order_book.model.OrderBookScenario'>)`

A limit order book fed by random order flow.

Example

```default
>>> model = OrderBook(OrderBookScenario(rng=1, steps=50))
>>> model.run()
>>> bool(model.best_ask() > model.best_bid())
True
```

Fill `window` levels on each side of the middle of the price grid.

#### `best_bid() → int`

Highest price with a resting buy order.

#### `best_ask() → int`

Lowest price with a resting sell order.

#### `mid() → float`

Mid price, halfway between the best quotes.

#### `rates() → ndarray`

Rates of the six event kinds in the current book.

#### `step() → None`

`events` order events, then record the mid price.

#### `event() → None`

Draw one event kind in proportion to its rate and apply it.

#### `limit(buy: bool) → None`

Rest one order `1 .. window` ticks inside the opposite best quote.

#### `cancel(side: ndarray) → None`

Remove one uniformly random resting order of `side`.

#### `returns() → ndarray`

Log returns of the mid price from one step to the next.

#### `run(steps: int | None = None) → None`

Run `steps` steps (the scenario’s `steps` by default).

#### `mid_price(model: OrderBook) → float`

The mid price (a model reporter).

#### `spread(model: OrderBook) → int`

The bid-ask spread in ticks (a model reporter).

Boltzmann wealth exchange: random pairs pass one unit of money.

`n` agents start with `money` units each. Every step the agents are split into random pairs (a uniformly random perfect matching; with an odd `n` one agent sits out), each pair picks a direction at random, and the giver passes one unit to the other if it has any. Money is conserved and never negative.

The Markov chain on configurations is symmetric: a transfer from `i` to `j` and its reverse have the same probability, one half of the probability of the matching. Its stationary law is therefore uniform over every way of sharing the `M = n * money` units among the `n` agents, and one agent’s wealth has the exact marginal `P(w = k) = C(M - k + n - 2, n - 2) / C(M + n - 1, n - 1)`, which tends to the geometric (discrete Boltzmann-Gibbs, exponential) law with mean `money` as `n` grows. Its Gini coefficient tends to one half.

Wealth is a `Column`, so a step is a handful of numpy operations on the whole table: no agent is visited in a Python loop.

Validation: the time-averaged Gini coefficient and the histogram of wealth after burn-in against `stationary_distribution()`, the exact marginal above.

References

Dragulescu, A. and Yakovenko, V. M. (2000). Statistical mechanics of money. European Physical Journal B, 17, 723-729.

#### `class Holder(model: M, *args, **kwargs)`

An agent holding an integer amount of money.

Create a new agent.

**Parameters:**

- **model** ([*Model*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.model.Model)) – The model instance in which the agent exists.
- **args** – Passed on to super.
- **kwargs** – Passed on to super.

Notes

to make proper use of python’s super, in each class remove the arguments and keyword arguments you need and pass on the rest to super

#### `property wealth`

Column(int64, default=0)

#### `class KineticScenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

Parameters of the Boltzmann wealth exchange.

**Variables:**

- **n** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – number of agents.
- **money** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – units of money every agent starts with (the mean wealth).
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – default run length used by `run`.

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `class KineticWealth(scenario: KineticScenario = <class 'modelly.zoo.kinetic_wealth.model.KineticScenario'>)`

Random pairwise exchange of single units of money.

Example

```default
>>> model = KineticWealth(KineticScenario(rng=1, n=100, steps=50))
>>> model.run()
>>> int(model.wealth.sum())
500
```

Create the agents, each with `money` units.

#### `property wealth: ndarray`

Every agent’s wealth (a live view of the column).

#### `step() → None`

One random matching; in each pair the giver passes a unit if it has one.

#### `run(steps: int | None = None) → None`

Run `steps` steps (the scenario’s `steps` by default).

#### `stationary_distribution() → ndarray`

Exact stationary `P(w = k)` for `k = 0 .. M`, uniform configurations.

#### `stationary_gini() → float`

Gini of the exact marginal: `E|X - Y| / (2 mean)`, `X, Y` independent.

For integer variables `E|X - Y| = 2 sum_k F(k) (1 - F(k))`.

#### `gini_of(model: KineticWealth) → float`

The Gini coefficient of the agents’ wealth (a model reporter).

Bouchaud-Mezard wealth condensation: random returns plus exchange.

Each agent’s wealth follows, in the mean-field version of the model, `dW_i = J (mean(W) - W_i) dt + sigma W_i dB_i` (Ito): an independent random return on what it holds, of variance `sigma^2` per unit time, and an exchange that pulls it toward the mean at rate `J`. A step of length `dt` applies the multiplicative part exactly, `W_i <- W_i exp(sigma sqrt(dt) xi_i - sigma^2 dt / 2)` with `xi_i` standard normal (mean preserving), then the exchange `W_i <- W_i + J dt (mean(W) - W_i)`, then divides by the mean, so `wealth` is relative wealth `w = W / mean(W)`.

The Fokker-Planck equation of `w` has the stationary density `P(w) ~ exp(-(alpha - 1) / w) / w^(1 + alpha)`, an inverse-gamma law with shape `alpha = 1 + 2 J / sigma^2` and scale `alpha - 1` (mean one): a Pareto tail of exponent `alpha`. Bouchaud and Mezard write the noise variance as `2 sigma^2`, hence their `mu = 1 + J / sigma^2`; with the convention here it is `1 + 2 J / sigma^2`. The larger `sigma^2 / J`, the fatter the tail and the more unequal the wealth.

Validation: the Gini coefficient of the simulated stationary wealth against the Gini of the inverse-gamma law (`stationary_shape()`), and its increase with `sigma^2 / J`.

References

Bouchaud, J.-P. and Mezard, M. (2000). Wealth condensation in a simple model of economy. Physica A, 282, 536-545.

#### `class Saver(model: M, *args, **kwargs)`

An agent holding a (relative) amount of wealth.

Create a new agent.

**Parameters:**

- **model** ([*Model*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.model.Model)) – The model instance in which the agent exists.
- **args** – Passed on to super.
- **kwargs** – Passed on to super.

Notes

to make proper use of python’s super, in each class remove the arguments and keyword arguments you need and pass on the rest to super

#### `property wealth`

Column(float64, default=1.0)

#### `class BouchaudMezardScenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

Parameters of the Bouchaud-Mezard model.

**Variables:**

- **n** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – number of agents.
- **exchange** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – exchange rate `J` per unit time.
- **volatility** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – `sigma`, the standard deviation of returns per unit time.
- **dt** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – length of a step; `exchange * dt` must be below one.
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – default run length used by `run`.

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `class BouchaudMezard(scenario: BouchaudMezardScenario = <class 'modelly.zoo.bouchaud_mezard.model.BouchaudMezardScenario'>)`

Multiplicative noise and mean-field exchange of wealth.

Example

```default
>>> model = BouchaudMezard(BouchaudMezardScenario(rng=1, n=100, steps=10))
>>> model.run()
>>> round(float(model.wealth.mean()), 6)
1.0
```

Create the agents, all with relative wealth one.

#### `property wealth: ndarray`

Every agent’s wealth relative to the mean (a live view of the column).

#### `step() → None`

Random returns, then exchange toward the mean, then renormalise.

#### `run(steps: int | None = None) → None`

Run `steps` steps (the scenario’s `steps` by default).

#### `stationary_shape() → float`

Shape `alpha = 1 + 2 J / sigma^2` of the stationary inverse-gamma law.

#### `gini_of(model: BouchaudMezard) → float`

The Gini coefficient of the agents’ wealth (a model reporter).

## Sociology and political science

Deffuant bounded-confidence opinion dynamics.

Every agent holds an opinion in `[0, 1]`. Two agents who meet compromise only when their opinions differ by less than the confidence bound `epsilon`: each moves a fraction `mu` of the way towards the other. A wide bound ends in consensus; a narrow one freezes the population into several opinion clusters, about `floor(1 / (2 epsilon))` of them for opinions drawn uniformly.

The original model picks one random pair per time step. Here one step is a sweep: the agents are put into a uniformly random perfect matching (a permutation cut into consecutive pairs) and every pair interacts at once, from the start-of-step opinions. The pairs are disjoint, so the updates do not interfere, and every agent meets exactly one uniformly random partner per step; a step is about `n / 2` events of the original dynamics, with the same kind of absorbing states (clusters more than `epsilon` apart). Opinions are a `Column`, so the sweep is three numpy operations.

Validation: one cluster for `epsilon = 0.4`, several for `epsilon = 0.1` (around `1 / (2 epsilon) = 5`), and a cluster count that does not grow as `epsilon` grows.

References

Deffuant, G., Neau, D., Amblard, F. and Weisbuch, G. (2000). Mixing beliefs among interacting agents. Advances in Complex Systems, 3, 87-98.

#### `class DeffuantScenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

Parameters of the Deffuant model.

**Variables:**

- **n** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – number of agents.
- **epsilon** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – confidence bound; agents further apart than this ignore each other.
- **mu** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – convergence parameter, the share of the difference each partner moves.
- **min_cluster_share** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – clusters with fewer agents than this share are not counted.
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – default run length of `run` (sweeps, each about `n / 2` meetings).

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `class Voter(model: M, *args, **kwargs)`

An agent with an opinion in `[0, 1]`.

Create a new agent.

**Parameters:**

- **model** ([*Model*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.model.Model)) – The model instance in which the agent exists.
- **args** – Passed on to super.
- **kwargs** – Passed on to super.

Notes

to make proper use of python’s super, in each class remove the arguments and keyword arguments you need and pass on the rest to super

#### `property opinion`

Column(float64, default=0.0)

#### `class Deffuant(scenario: DeffuantScenario = <class 'modelly.zoo.deffuant.model.DeffuantScenario'>)`

Random pairs compromise when their opinions are within `epsilon`.

Example

```default
>>> model = Deffuant(DeffuantScenario(rng=1, epsilon=0.4, steps=200))
>>> model.run()
>>> model.n_clusters()
1
```

Create `n` voters with uniform random opinions.

#### `step() → None`

One sweep: a random perfect matching, every close pair compromises.

#### `run(steps: int | None = None) → None`

Run `steps` sweeps (the scenario’s `steps` by default).

#### `n_clusters() → int`

Opinion clusters holding at least `min_cluster_share` of the agents.

#### `cluster_count(model: Deffuant) → int`

The number of opinion clusters (a model reporter).

#### `spread(model: Deffuant) → float`

Standard deviation of the opinions (a model reporter).

Hegselmann-Krause bounded-confidence opinion dynamics.

Every agent holds an opinion in `[0, 1]`. At each step, all at once, every agent moves to the mean opinion of the agents within `epsilon` of its own (itself included). Agents further apart never influence each other, so the population splits into clusters that stop moving after a finite number of steps; a wide bound ends in consensus.

The confidence set of an agent is a contiguous range of the sorted opinions, found with two binary searches, and its mean comes from a running sum, so a step costs `O(n log n)` instead of the `O(n^2)` of comparing every pair. The run stops (`running` turns `False`) when no opinion moves by more than `tolerance`.

Validation: consensus for `epsilon = 0.3`, several clusters for narrow bounds, a cluster count that falls as `epsilon` grows, and identical steps to the plain `O(n^2)` definition.

References

Hegselmann, R. and Krause, U. (2002). Opinion dynamics and bounded confidence: models, analysis and simulation. Journal of Artificial Societies and Social Simulation, 5(3).

#### `class HKScenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

Parameters of the Hegselmann-Krause model.

**Variables:**

- **n** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – number of agents.
- **epsilon** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – confidence bound; an agent averages the opinions within it.
- **tolerance** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the run stops when no opinion moves by more than this.
- **min_cluster_share** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – clusters with fewer agents than this share are not counted.
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – maximum run length of `run`.

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `class Voter(model: M, *args, **kwargs)`

An agent with an opinion in `[0, 1]`.

Create a new agent.

**Parameters:**

- **model** ([*Model*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.model.Model)) – The model instance in which the agent exists.
- **args** – Passed on to super.
- **kwargs** – Passed on to super.

Notes

to make proper use of python’s super, in each class remove the arguments and keyword arguments you need and pass on the rest to super

#### `property opinion`

Column(float64, default=0.0)

#### `confidence_means(x: ndarray, epsilon: float) → ndarray`

For every opinion, the mean of the opinions within `epsilon` of it.

Example

```default
>>> confidence_means(np.array([0.0, 0.1, 0.9]), 0.2).round(2).tolist()
[0.05, 0.05, 0.9]
```

#### `class HegselmannKrause(scenario: HKScenario = <class 'modelly.zoo.hegselmann_krause.model.HKScenario'>)`

Every agent moves to the mean of the opinions within its confidence bound.

Example

```default
>>> model = HegselmannKrause(HKScenario(rng=1, epsilon=0.3))
>>> model.run()
>>> model.n_clusters(), model.running
(1, False)
```

Create `n` voters with uniform random opinions.

#### `step() → None`

Synchronous update; stop once the opinions no longer move.

#### `run(steps: int | None = None) → None`

Step until the opinions settle, at most `steps` times (scenario default).

#### `n_clusters() → int`

Opinion clusters holding at least `min_cluster_share` of the agents.

#### `cluster_count(model: HegselmannKrause) → int`

The number of opinion clusters (a model reporter).

#### `spread(model: HegselmannKrause) → float`

Standard deviation of the opinions (a model reporter).

Axelrod’s model of the dissemination of culture.

Every site of a square grid holds a culture: `features` features, each taking one of `traits` values. At each event a random site and a random neighbour interact with probability equal to their cultural overlap (the share of features on which they agree); when they interact, the site copies one of the features on which they differ. Similar neighbours become more similar, and neighbours with nothing in common never interact, so the grid freezes into regions of identical culture. Few traits per feature end in a single culture; many traits leave many regions (the transition studied by Castellano, Marsili and Vespignani).

The sites are the rows of a `CellIndex` over a von Neumann grid, the cultures one `(n_sites, features)` integer array. Events stay sequential, as in the original, but a step pre-draws `events_per_step` sites, neighbours (`CellIndex.random_neighbor`) and uniforms in three numpy calls and runs the events on plain lists. After each step the model checks, over every bond at once, whether a pair with partial overlap is left; when none is, the culture map is frozen and `running` turns `False`. Cultural regions are the connected components of the bonds with full overlap.

Validation: with five features on a 10 x 10 grid, two traits end in one region for most seeds and thirty traits in many; the mean number of regions grows with the traits.

References

Axelrod, R. (1997). The dissemination of culture: a model with local convergence and global polarization. Journal of Conflict Resolution, 41(2), 203-226.

Castellano, C., Marsili, M. and Vespignani, A. (2000). Nonequilibrium phase transition in a model for social influence. Physical Review Letters, 85(16), 3536-3539.

#### `class AxelrodScenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

Parameters of Axelrod’s culture model.

**Variables:**

- **width** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – grid width (sites).
- **height** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – grid height (sites).
- **features** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – cultural features per site.
- **traits** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – values each feature can take.
- **events_per_step** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – interactions attempted per step.
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – maximum run length of `run`; it stops earlier once the map is frozen.

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `class Axelrod(scenario: AxelrodScenario = <class 'modelly.zoo.axelrod.model.AxelrodScenario'>)`

Sites copy cultural traits from similar neighbours until no bond is active.

Example

```default
>>> model = Axelrod(AxelrodScenario(rng=1, traits=2))
>>> model.run()
>>> model.running, model.n_regions()
(False, 1)
```

Draw a uniformly random culture for every site.

#### `step() → None`

Run `events_per_step` events, then stop if no bond is active.

#### `run(steps: int | None = None) → None`

Step until the map is frozen, at most `steps` times (scenario default).

#### `overlaps() → ndarray`

Number of shared features across every bond.

#### `n_regions() → int`

Connected regions of identical culture.

#### `interact(site: list[int], partner: list[int], accept: float, pick: float) → None`

One event: with probability overlap / F, `site` copies one differing feature.

#### `region_count(model: Axelrod) → int`

The number of cultural regions (a model reporter).

#### `active_bonds(model: Axelrod) → int`

Bonds whose sites share some but not all features (a model reporter).

## Transport and energy

Nagel-Schreckenberg traffic on a ring road.

A single-lane ring road of `length` cells, each holding at most one car. Every step, all cars update in parallel:

1. accelerate: `v = min(v + 1, max_speed)`;
1. brake to the gap: `v = min(v, gap)`, the number of empty cells to the car ahead;
1. dawdle: with probability `dawdle`, `v = max(v - 1, 0)`;
1. move `v` cells forward.

Cars are `Car` agents whose `position` and `velocity` are `Column` attributes, so the whole road updates with a handful of numpy operations on the column table. Cars never overtake, so the rows stay in road order (cyclically) and the car ahead of row `i` is row `i + 1`.

Validation: the fundamental diagram, flow `J = density * mean speed` against density. Without dawdling the steady-state flow is exactly `min(density * max_speed, 1 - density)`: free flow below the critical density `1 / (max_speed + 1)`, a jam moving backwards above it. With dawdling the flow rises with density, peaks at an interior density and falls; at low density every car runs at `max_speed - 1` with probability `dawdle` and at `max_speed` otherwise, so `J = density * (max_speed - dawdle)`.

References

Nagel, K. and Schreckenberg, M. (1992). A cellular automaton model for freeway traffic. Journal de Physique I, 2(12), 2221-2229.

#### `class TrafficScenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

Parameters of the Nagel-Schreckenberg model.

**Variables:**

- **length** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – number of cells of the ring road.
- **density** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – share of cells holding a car.
- **max_speed** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the speed limit, in cells per step.
- **dawdle** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – probability per step that a car slows down by one for no reason.
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – default run length used by `run`.

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `class Car(model: M, *args, **kwargs)`

A car: its cell on the ring and its speed, both stored in columns.

Create a new agent.

**Parameters:**

- **model** ([*Model*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.model.Model)) – The model instance in which the agent exists.
- **args** – Passed on to super.
- **kwargs** – Passed on to super.

Notes

to make proper use of python’s super, in each class remove the arguments and keyword arguments you need and pass on the rest to super

#### `property position`

Column(int64, default=0)

#### `property velocity`

Column(int64, default=0)

#### `class NagelSchreckenberg(scenario: TrafficScenario = <class 'modelly.zoo.nagel_schreckenberg.model.TrafficScenario'>)`

Cars on a ring road, updated in parallel on their column table.

Example

```default
>>> model = NagelSchreckenberg(TrafficScenario(rng=1, steps=20))
>>> model.run()
>>> len(model.cars) == round(0.15 * 1000)
True
```

Place the cars on distinct random cells, standing still.

#### `gaps() → ndarray`

Empty cells between every car and the car ahead of it.

#### `step() → None`

Accelerate, brake to the gap, dawdle, move: all cars at once.

#### `run(steps: int | None = None) → None`

Run `steps` steps (the scenario’s `steps` by default).

#### `property mean_speed: float`

Mean speed of the cars, in cells per step.

#### `property flow: float`

density times mean speed.

**Type:**

Cars passing a point per step

#### `fundamental_diagram(densities, transient: int, measured: int, **params) → list`

Mean flow after `transient` steps, over `measured` steps, at each density.

`params` are the other `TrafficScenario` parameters (`rng`, `dawdle`…).

Example

```default
>>> flows = fundamental_diagram([0.1, 0.5], 50, 50, rng=1, dawdle=0.0)
>>> [round(f, 2) for f in flows]
[0.5, 0.5]
```

Bass diffusion of an innovation (rooftop solar, heat pumps) on a network.

Every household either has adopted the innovation or not. In each step of length `dt` (in years) a household that has not adopted does so with probability `(innovation + imitation * share) * dt`: `innovation` is the pull of advertising and `imitation` the pull of the households it knows, `share` being the share of its neighbours that have adopted. With `mixing="well-mixed"` the share is that of the whole population, as in Bass’s original model; with `mixing="network"` it is over the household’s neighbours in a random network of mean degree `degree` (a `MultilayerNetwork` with one layer), so the infection pressure is one sparse product per step.

Households are `Household` agents whose `adopted` flag is a `Column`; the whole population adopts in one `ColumnTable.draw`.

Validation: in the well-mixed limit the expected cumulative adoption follows the Bass equation `dF/dt = (innovation + imitation * F) * (1 - F)`, whose solution is `F(t) = (1 - exp(-(p + q) t)) / (1 + (q / p) exp(-(p + q) t))` with `p = innovation` and `q = imitation`; `bass_curve` evaluates it. On a dense random network the curve stays close to it; on a sparse one adoption is slower, because non-adopters cluster together and see fewer adopters than the population average.

References

Bass, F. M. (1969). A new product growth for model consumer durables. Management Science, 15(5), 215-227.

#### `class BassScenario(*, rng: Generator | BitGenerator | int | integer | Sequence[int] | SeedSequence | None = None, scenario_id: int | None = None, replication_id: int = -1, **kwargs: Any)`

Parameters of the Bass diffusion model.

**Variables:**

- **households** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – number of households.
- **innovation** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – Bass `p`, adoption rate per year from outside influence.
- **imitation** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – Bass `q`, adoption rate per year when every neighbour has adopted.
- **dt** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – length of a step, in years.
- **mixing** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – `"well-mixed"` (share over everybody) or `"network"`.
- **degree** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – mean number of neighbours in the random network.
- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – default run length used by `run`.

Initialize a Scenario.

**Parameters:**

- **rng** – Seed for the random number generator. Accepts any value accepted by numpy.random.default_rng(). scenario.rng is always a Generator after initialisation. The initial seed sequence is stored in scenario.seed_sequence and used by spawn_replications() to derive child seeds.
- **scenario_id** – Index of the design point in the experiment matrix.
- **replication_id** – Index of the stochastic replication for this design point. defaults to PARENT_REPLICATION_ID (-1). It is advised to use spawn_replications() to create replications for a given scenario, rather than handling this yourself.
- ****kwargs** – All other scenario parameters (override class-level defaults).

#### `class Household(model: M, *args, **kwargs)`

A household; `adopted` is 1 once it has adopted.

Create a new agent.

**Parameters:**

- **model** ([*Model*](https://remipelloux.github.io/Modelly/dev/apis/core.html#modelly.core.model.Model)) – The model instance in which the agent exists.
- **args** – Passed on to super.
- **kwargs** – Passed on to super.

Notes

to make proper use of python’s super, in each class remove the arguments and keyword arguments you need and pass on the rest to super

#### `property adopted`

Column(int8, default=0)

#### `class BassDiffusion(scenario: BassScenario = <class 'modelly.zoo.bass_diffusion.model.BassScenario'>)`

Households adopting from advertising and from their neighbours.

Example

```default
>>> model = BassDiffusion(BassScenario(rng=1, steps=50))
>>> model.run()
>>> 0 < model.adoption < 1
True
```

Create the households and, for `mixing="network"`, their network.

#### `random_network() → MultilayerNetwork`

An Erdos-Renyi-like graph: `households * degree / 2` random distinct pairs.

#### `neighbour_share() → ndarray | float`

Share of adopters among each household’s neighbours (or everybody’s).

#### `step() → None`

Every non-adopter adopts with probability `(p + q * share) * dt`.

#### `run(steps: int | None = None) → None`

Run `steps` steps (the scenario’s `steps` by default).

#### `property adoption: float`

Share of households that have adopted.

#### `property time_in_years: float`

steps times `dt`.

**Type:**

Elapsed time in years

#### `bass_curve(t: ndarray, innovation: float, imitation: float) → ndarray`

The Bass solution `F(t)`: cumulative share adopted at time `t`, from `F(0) = 0`.

Example

```default
>>> float(bass_curve(np.array([0.0]), 0.03, 0.38)[0])
0.0
```
