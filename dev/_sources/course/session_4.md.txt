# Session 4: networks and contact structure

**Zoo models:** [Bass diffusion](../zoo/bass_diffusion.md),
[age-structured SEIR](../zoo/age_seir.md)

## Goals

- Represent who-influences-whom as a network, and an influence step as one sparse product.
- Compare a well-mixed model with the same model on a network.
- Summarise a network by a contact matrix between groups and use it in a compartmental model.

**Before the session:** [Networks](../networks.md).

## Exercises

**4.1** Run the Bass model well mixed and on random networks of mean degree 4 and 50. When
does each reach half adoption?

<details>
<summary>Solution</summary>

```python
from modelly.zoo.bass_diffusion.model import BassDiffusion, BassScenario

for params in (
    {"mixing": "well-mixed"},
    {"mixing": "network", "degree": 4},
    {"mixing": "network", "degree": 50},
):
    model = BassDiffusion(BassScenario(rng=1, **params))
    model.run()
    frame = model.datacollector.get_model_vars_dataframe()
    print(params, frame["time"][frame["adoption"] >= 0.5].iloc[0])
```

The dense network is indistinguishable from mixing; the sparse one is later.

</details>

**4.2** Why does a sparse network slow imitation down, when every household has the same
`p` and `q`?

<details>
<summary>Solution</summary>

Adopters and non-adopters cluster: early adopters' neighbours adopt by imitation, so the
non-adopters left over tend to have non-adopting neighbours, and see a lower share of
adopters than the population average. In the well-mixed model everybody sees the average.

</details>

**4.3** Build a population of 600 people with households (all pairs linked) and workplaces
of 8 with `MultilayerNetwork`, give everybody an age, and compute its contact matrix for
the groups under 18, 18 to 64, and 65 and over.

<details>
<summary>Solution</summary>

```python
import numpy as np

from modelly.space.networks import MultilayerNetwork, age_groups, contact_matrix

rng = np.random.default_rng(1)
n = 600
ages = rng.integers(0, 90, n)
network = MultilayerNetwork(n, {"household": 1.0, "work": 0.5})
for start in range(0, n, 3):  # households of three
    members = range(start, min(start + 3, n))
    network.add_edges([(u, v) for u in members for v in members if u < v], "household")
workers = rng.permutation(np.flatnonzero((ages >= 18) & (ages < 65)))
for start in range(0, len(workers), 8):
    team = workers[start : start + 8].tolist()
    network.add_edges([(u, v) for u in team for v in team if u < v], "work")
groups = age_groups(ages, [18, 65])
print(contact_matrix(network, groups))
```

</details>

**4.4** Use that matrix as the `contacts` of `SEIRScenario` (with matching `group_sizes`)
and report `r0()` and the final size by group.

<details>
<summary>Solution</summary>

```python
from modelly.zoo.age_seir.model import AgeSEIR, SEIRScenario

matrix = contact_matrix(network, groups)
sizes = tuple(int(k) for k in np.bincount(groups, minlength=3))
model = AgeSEIR(
    SEIRScenario(
        rng=1,
        group_sizes=sizes,
        contacts=tuple(map(tuple, matrix)),
        beta=0.1,
        initial_infected=(1, 1, 1),
    )
)
print(model.r0(), model.final_size())
```

Adults, who have both household and work contacts, have the largest final size.

</details>
