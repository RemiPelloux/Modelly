# Age-structured SEIR with contact matrices

**Field:** epidemiology · **Zoo name:** `age_seir` · **Module:** `modelly.zoo.age_seir.model`

![Epidemic curves of three age groups](https://remipelloux.github.io/Modelly/_images/age_seir.png)

People are split into age groups and are susceptible, exposed, infectious or recovered. A susceptible of group `a` is infected in one step with probability `1 - exp(-beta * sum_b C[a, b] * I_b / N_b)`, where `C[a, b]` is the mean number of contacts a member of `a` has with members of `b` per step. Exposed people become infectious with probability `incubation` per step, infectious people recover with probability `recovery`.

## How it is written

Everybody in the same group and state faces the same probabilities, so the population is a `CohortTable` with one row per (group, state), and each transition is one binomial draw per row. That has exactly the law of one draw per person (see [Vectorised step phases](https://remipelloux.github.io/Modelly/vectorised_phases.html)), and a population of a million costs the same as one of a hundred. A contact matrix measured on a synthetic population comes from `modelly.space.networks.contact_matrix`; see [Networks](https://remipelloux.github.io/Modelly/networks.html).

```python
from modelly.zoo.age_seir.model import AgeSEIR, SEIRScenario

model = AgeSEIR(SEIRScenario(rng=42))
model.run()
model.r0(), model.attack_rate(), model.final_size()
model.datacollector.get_model_vars_dataframe()  # S, E, I, R per step
```

Parameter

Default

Meaning

group_sizes

(20000, 60000, 20000)

people per age group (children, adults, seniors)

contacts

3 x 3, reciprocal

C[a][b], contacts per step of a member of a with members of b

beta

0.035

transmission probability per contact

incubation

0.25

probability per step that an exposed person becomes infectious

recovery

0.2

probability per step that an infectious person recovers

initial_infected

(10, 10, 10)

infectious people per group at the start

vaccinated

()

people immune from the start, per group (none by default)

steps

400

run length of run()

The default contact matrix is illustrative, not survey data.

To start from a synthetic population (people in households, schools and workplaces, built from census tables with `modelly.population`), `scenario_from_population` counts the age groups and measures the contact matrix on the population’s contact network; see [Synthetic populations](https://remipelloux.github.io/Modelly/population.html#starting-the-age-structured-seir-model). The default scenario does not change.

```python
from modelly.population import contact_network
from modelly.zoo.age_seir.model import AgeSEIR, scenario_from_population

network = contact_network(people, model.rng)
seir = AgeSEIR(
    scenario_from_population(people, network, ("0-17", "18-64", "65+"), rng=5)
)
```

## Validation

Summing the force of infection over the whole epidemic gives the final-size relation `log(s_a) = log(s0_a) - (beta / recovery) * sum_b C[a, b] * (1 - s_b)`, where `s_a` is the share of group `a` never infected. With one group it is the Kermack-McKendrick relation `s = s0 * exp(-R0 * (1 - s))`, with `R0 = beta * C / recovery`. `final_size()` solves it.

`tests/zoo/test_age_seir.py` runs a homogeneous population of 200,000, written both as one group and as three equal groups, with three seeds, and checks the simulated attack rate is within five standard deviations of the final-size relation, the standard deviation coming from the central limit theorem for the final size (Andersson and Britton). It also checks the three age groups against the multi-group relation, that an outbreak with `R0 < 1` stays small, that nobody is created or lost, and that the same seed gives the same epidemic curve.

## Model card: Age-structured SEIR with contact matrices

An SEIR epidemic over age groups that mix through a contact matrix, written as binomial cohorts so a million people cost what a hundred do.

**Model:** `modelly.zoo.age_seir.model:AgeSEIR` · **Validated:** 2026-11-03 with Modelly 1.5.0.dev0, on source `bd3b5f410549`

### Intended use

- Teaching how age mixing shapes an epidemic: attack rates by group, the role of the contact matrix, R0 as a spectral radius.
- A starting point for age-structured epidemic models, with a validated core to extend (vaccination, interventions on contacts).
- Comparing scenarios in relative terms (contact reductions in one group against another) on a stated contact matrix.

### Out-of-scope use

- Forecasting a real epidemic: the default contact matrix is illustrative, not survey data, and nothing is calibrated.
- Decisions about a specific population without a contact matrix measured on it (social-contact surveys, or `scenario_from_population`).
- Diseases whose natural history is not SEIR with geometric periods (waning immunity, asymptomatic carriers, age-dependent severity).

### Data

- None by default: group sizes, the 3 x 3 contact matrix and the rates are illustrative values in `SEIRScenario`.
- Optionally, a synthetic population from census tables (`modelly.population`), from which `scenario_from_population` takes group sizes and measures the contact matrix.

### Validation

Check

Test

attack rate within five standard deviations of the final-size relation (one group and three equal groups, three seeds)

tests/zoo/test_age_seir.py::test_final_size_relation_homogeneous

each age group’s attack rate against the multi-group final-size relation

tests/zoo/test_age_seir.py::test_final_size_by_age_group

with vaccinated people in one group, each group’s attack rate follows the final-size relation without them

tests/zoo/test_age_seir.py::test_final_size_with_vaccination

an outbreak with R0 below one stays small; nobody is created or lost; same seed, same epidemic

tests/zoo/test_age_seir.py

### Known limits

- Homogeneous mixing within each age group: no households, places or networks, so local saturation and clustering are absent.
- One step is one unit of time with transitions drawn once per step; the exposed and infectious periods are geometric, not fixed or gamma-distributed.
- Closed population: no births, deaths or migration, so runs longer than one epidemic wave are not meaningful.
- The final-size check validates the transmission core, not the time course: peak timing depends on the step and the periods.

### Ethical considerations

- Age-targeted results (who to protect or restrict first) affect real groups; present them with their intervals and with the assumptions above, never as a forecast.
- An illustrative contact matrix can make one age group look responsible for spread; say where the matrix comes from whenever results are shown.

## References

- Kermack, W. O. and McKendrick, A. G. (1927). A contribution to the mathematical theory of epidemics. *Proceedings of the Royal Society A*, 115, 700-721.
- Mossong, J. et al. (2008). Social contacts and mixing patterns relevant to the spread of infectious diseases. *PLoS Medicine*, 5(3), e74.
- Andersson, H. and Britton, T. (2000). *Stochastic Epidemic Models and Their Statistical Analysis*. Lecture Notes in Statistics 151, Springer.

Start a project from it with `modelly zoo copy age_seir my_epidemic`.
