---
file_format: mystnb
kernelspec:
  name: python3
  display_name: Python 3
---

# Epidemiology: who gets infected, and how many

How many people will an epidemic infect, and in which age groups? This tutorial runs the
[age-structured SEIR model](../../zoo/age_seir.md) from the zoo, checks it against the
final-size relation, and uses the contact matrix to compare two interventions.

Start a project from it with `modelly zoo copy age_seir my_epidemic` (the same command in
bash and PowerShell).

## Build and run

A hundred thousand people in three age groups. `contacts[a][b]` is the mean number of
contacts a member of group `a` has with members of group `b` per day; it is reciprocal, so
`N[a] * C[a, b] == N[b] * C[b, a]`. In a real study it comes from a contact survey, or from a
synthetic population through `modelly.space.networks.contact_matrix`.

```{code-cell} ipython3
import numpy as np
import matplotlib.pyplot as plt

from modelly.zoo.age_seir.model import AgeSEIR, SEIRScenario, State

GROUPS = ("children", "adults", "seniors")
scenario = SEIRScenario(rng=42)
model = AgeSEIR(scenario)
print(f"R0 = {model.r0():.2f}")
model.run()
model.datacollector.get_model_vars_dataframe().iloc[::50]
```

The population is a table of cohorts, one row per (age group, state), so the run costs the
same for a hundred thousand people as for a hundred:

```{code-cell} ipython3
model.people.to_dataframe()
```

## Plot: the epidemic curve

```{code-cell} ipython3
model = AgeSEIR(scenario)
infectious = []
for _ in range(scenario.steps):
    model.step()
    infectious.append(model.counts()[:, State.I] / model.sizes)
fig, ax = plt.subplots(figsize=(6, 3.5))
ax.plot(np.array(infectious), label=GROUPS)
ax.set_xlabel("day")
ax.set_ylabel("share infectious")
ax.legend(frameon=False);
```

## Check: the final-size relation

Over the whole epidemic the share `s_a` of group `a` that escapes infection solves
`log(s_a) = log(s0_a) - (beta / recovery) * sum_b C[a, b] * (1 - s_b)`. `final_size()`
solves it; the simulated attack rates agree to within the sampling noise.

```{code-cell} ipython3
import pandas as pd

pd.DataFrame(
    {"simulated": model.attack_rate(), "final-size relation": model.final_size()},
    index=GROUPS,
).round(3)
```

## Analysis: which intervention?

Halving the contacts among children (closing schools) and halving every contact of the
seniors (shielding) reduce `R0` differently, and protect different groups.

```{code-cell} ipython3
contacts = np.array(scenario.contacts)
schools = contacts.copy()
schools[0, 0] /= 2
shielding = contacts.copy()
shielding[2, :] /= 2
shielding[:, 2] /= 2
rows = {}
for label, matrix in {"none": contacts, "schools": schools, "shielding": shielding}.items():
    run = AgeSEIR(SEIRScenario(rng=42, contacts=tuple(map(tuple, matrix))))
    run.run()
    rows[label] = [run.r0(), *run.attack_rate()]
pd.DataFrame(rows, index=["R0", *GROUPS]).T.round(3)
```

## Going further

- Build the contact matrix from a synthetic population with households, schools and
  workplaces; see [Networks](../../networks.md) and the layered epidemic example.
- Make `beta` a function of time to model a lockdown.
- Fit `beta` to an observed epidemic curve.
