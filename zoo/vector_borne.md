# Vector-borne transmission on a landscape

**Field:** epidemiology · **Zoo name:** `vector_borne` · **Module:** `modelly.zoo.vector_borne.model`

![Infectious hosts for three vector densities](https://remipelloux.github.io/Modelly/_images/vector_borne.png)

Hosts live on the cells of a landscape grid and move to a random neighbouring cell with probability `move` per day; each is susceptible, infectious or recovered. Mosquitoes live in the cells too, `m` per host on average (times a per-cell `habitat` suitability), and are susceptible, exposed (the extrinsic incubation) or infectious. Every day a mosquito survives with probability `survival` and bites `a` times, each time a random host of its cell. An infectious bite infects a susceptible host with probability `b`; a bite on an infectious host infects a susceptible mosquito with probability `c`. New mosquitoes emerge to keep the density at `m`.

## How it is written

Mosquitoes in the same cell and state are interchangeable, so they are a `CohortTable` with one row per (cell, state): survival, infection and incubation are binomial draws per row. Hosts are agents with `Column` arrays for their state and cell row, placed by row with `CellIndex.track` and moved with `CellIndex.random_neighbor`. A habitat raster, for example the values of a `modelly.space.geo.RasterLayer`, sets where the mosquitoes are: `VectorScenario(habitat=...)`.

```python
from modelly.zoo.vector_borne.model import VectorBorne, VectorScenario

model = VectorBorne(VectorScenario(rng=42, m=2.0))
model.r0()  # Ross-Macdonald R0
model.run()  # stops when the infection is gone
model.attack_rate()
```

Parameter

Default

Meaning

width, height

10, 10

landscape size in cells

hosts_per_cell

20

hosts per cell at the start

habitat

None

per-cell suitability scaling the vector density, shape (width, height)

m

2.0

mosquitoes per host

a

0.3

bites per mosquito per day

b, c

0.5, 0.5

transmission probability per bite, mosquito to host and host to mosquito

survival

0.9

daily survival of a mosquito

incubation

0.1

daily probability that an exposed mosquito becomes infectious

recovery

0.1

daily probability that an infectious host recovers

move

0.3

daily probability that a host moves to a neighbouring cell

initial_infected

10

infectious hosts at the start

steps

600

maximum run length of run()

## Validation

The Ross-Macdonald reproduction number, host to host over one full cycle, is `R0 = m a^2 b c P / (recovery (1 - survival))`, where `P` is the probability that an infected mosquito survives the extrinsic incubation; `r0()` computes it for the discrete daily cycle of the model. It is linear in the vector density `m`.

`tests/zoo/test_vector_borne.py` runs vector densities 0.5, 2 and 4 (R0 about 0.5, 2.1 and 4.3) with three seeds, and checks for every seed that the attack rates come out in the order of R0, that the subcritical outbreak stays under 5 % (its expected size is about 1 %), and that R0 = 4 infects over 80 % of the hosts. Spatial structure keeps the attack rates below the well-mixed final size. It also checks that the habitat raster confines the mosquitoes, that hosts are conserved, and that the same seed gives the same epidemic curve.

## Model card: Vector-borne transmission on a landscape

Ross-Macdonald transmission between hosts that move on a landscape grid and mosquitoes held as binomial cohorts per cell, with an optional habitat raster setting where the mosquitoes are.

**Model:** `modelly.zoo.vector_borne.model:VectorBorne` · **Validated:** 2026-11-03 with Modelly 1.4.3, on source `ee8b354bc1e7`

### Intended use

- Teaching the Ross-Macdonald model: how vector density, biting rate, mosquito survival and incubation combine into R0, and why R0 is linear in the density `m`.
- Exploring in relative terms how a habitat raster and host movement shape where and how far an outbreak spreads.
- A starting point for vector-borne models on real landscapes, with a validated transmission core to extend (vector control, seasonality, more host states).

### Out-of-scope use

- Forecasting a real malaria, dengue or other vector-borne outbreak: the bionomics are illustrative and nothing is calibrated.
- Planning vector control for a specific place without entomological data measured there (densities, biting and survival rates, habitat).
- Diseases with a host latent period, waning immunity, several vector species or human-to-human transmission, none of which the model has.

### Data

- None by default: the 10 x 10 landscape, 20 hosts per cell and the daily rates are illustrative values in `VectorScenario`.
- Optionally, a habitat suitability raster of shape `(width, height)`, for example the values of a `modelly.space.geo.RasterLayer`, passed as `habitat`.

### Validation

Check

Test

R0 is linear in the vector density, below one at m = 0.5 and above one at m = 2 and 4, and matches the Ross-Macdonald formula

tests/zoo/test_vector_borne.py::test_r0_is_linear_in_vector_density

attack rates come out in the order of R0 for three seeds: under 5 % when R0 < 1, over 80 % at R0 about 4

tests/zoo/test_vector_borne.py::test_attack_rates_follow_r0

a habitat raster confines the mosquitoes; hosts are conserved; same seed, same epidemic

tests/zoo/test_vector_borne.py

### Known limits

- Mosquitoes do not move between cells and bite only hosts of their own cell, chosen at random; hosts move to a random neighbouring cell.
- One step is one day with every transition drawn once per step, so the infectious and incubation periods are geometric.
- Emergence keeps the vector density at `m`: no seasonality, weather or density dependence in the mosquito population.
- Closed host population with no births, deaths or loss of immunity; the validation orders outbreak sizes by R0, it does not check the time course.

### Ethical considerations

- Results about where an outbreak spreads can steer spraying, bed-net or other resources towards some communities and away from others; present them as illustrative, with the assumptions above.
- A habitat raster can make one area look like the source of transmission; say where the raster comes from whenever results are shown.

## References

- Ross, R. (1911). *The Prevention of Malaria*, 2nd ed. John Murray.
- Macdonald, G. (1957). *The Epidemiology and Control of Malaria*. Oxford University Press.

Start a project from it with `modelly zoo copy vector_borne my_vector_model`.
