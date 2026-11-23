# Vector-borne transmission on a landscape

**Field:** epidemiology · **Zoo name:** `vector_borne` · **Module:** `modelly.zoo.vector_borne.model`

![Infectious hosts for three vector densities](../images/gallery/vector_borne.png)

Hosts live on the cells of a landscape grid and move to a random neighbouring cell with
probability `move` per day; each is susceptible, infectious or recovered. Mosquitoes live in the
cells too, `m` per host on average (times a per-cell `habitat` suitability), and are
susceptible, exposed (the extrinsic incubation) or infectious. Every day a mosquito survives
with probability `survival` and bites `a` times, each time a random host of its cell. An
infectious bite infects a susceptible host with probability `b`; a bite on an infectious host
infects a susceptible mosquito with probability `c`. New mosquitoes emerge to keep the density
at `m`.

## How it is written

Mosquitoes in the same cell and state are interchangeable, so they are a `CohortTable` with one
row per (cell, state): survival, infection and incubation are binomial draws per row. Hosts are
agents with `Column` arrays for their state and cell row, placed by row with `CellIndex.track`
and moved with `CellIndex.random_neighbor`. A habitat raster, for example the values of a
`modelly.space.geo.RasterLayer`, sets where the mosquitoes are: `VectorScenario(habitat=...)`.

```python
from modelly.zoo.vector_borne.model import VectorBorne, VectorScenario

model = VectorBorne(VectorScenario(rng=42, m=2.0))
model.r0()  # Ross-Macdonald R0
model.run()  # stops when the infection is gone
model.attack_rate()
```

| Parameter | Default | Meaning |
|---|---|---|
| `width`, `height` | `10`, `10` | landscape size in cells |
| `hosts_per_cell` | `20` | hosts per cell at the start |
| `habitat` | `None` | per-cell suitability scaling the vector density, shape `(width, height)` |
| `m` | `2.0` | mosquitoes per host |
| `a` | `0.3` | bites per mosquito per day |
| `b`, `c` | `0.5`, `0.5` | transmission probability per bite, mosquito to host and host to mosquito |
| `survival` | `0.9` | daily survival of a mosquito |
| `incubation` | `0.1` | daily probability that an exposed mosquito becomes infectious |
| `recovery` | `0.1` | daily probability that an infectious host recovers |
| `move` | `0.3` | daily probability that a host moves to a neighbouring cell |
| `initial_infected` | `10` | infectious hosts at the start |
| `steps` | `600` | maximum run length of `run()` |

## Validation

The Ross-Macdonald reproduction number, host to host over one full cycle, is
`R0 = m a^2 b c P / (recovery (1 - survival))`, where `P` is the probability that an infected
mosquito survives the extrinsic incubation; `r0()` computes it for the discrete daily cycle of
the model. It is linear in the vector density `m`.

`tests/zoo/test_vector_borne.py` runs vector densities 0.5, 2 and 4 (R0 about 0.5, 2.1 and 4.3)
with three seeds, and checks for every seed that the attack rates come out in the order of R0,
that the subcritical outbreak stays under 5 % (its expected size is about 1 %), and that R0 = 4
infects over 80 % of the hosts. Spatial structure keeps the attack rates below the well-mixed
final size. It also checks that the habitat raster confines the mosquitoes, that hosts are
conserved, and that the same seed gives the same epidemic curve.

## References

- Ross, R. (1911). *The Prevention of Malaria*, 2nd ed. John Murray.
- Macdonald, G. (1957). *The Epidemiology and Control of Malaria*. Oxford University Press.

Start a project from it with `modelly zoo copy vector_borne my_vector_model`.
