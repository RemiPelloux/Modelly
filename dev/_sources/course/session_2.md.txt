# Session 2: data, seeds and reproducibility

**Zoo models:** [Boltzmann wealth exchange](../zoo/kinetic_wealth.md),
[Bouchaud-Mezard](../zoo/bouchaud_mezard.md)

## Goals

- Collect model-level data with a `DataCollector` and turn it into a pandas DataFrame.
- Understand why every draw must come from `model.rng` or `model.random`, and check that the
  same seed gives the same run.
- Tell apart a transient from a stationary state, and average only the latter.

**Before the session:** the [collecting data](../tutorials/5_collecting_data.ipynb)
tutorial and [Checking a model](../lint.md).

## Exercises

**2.1** Run Bouchaud-Mezard twice with `rng=7` and once with `rng=8`. Show that the first
two Gini series are identical and the third is not.

<details>
<summary>Solution</summary>

```python
from modelly.zoo.bouchaud_mezard.model import BouchaudMezard, BouchaudMezardScenario


def gini_series(seed):
    model = BouchaudMezard(BouchaudMezardScenario(rng=seed, steps=300))
    model.run()
    return model.datacollector.get_model_vars_dataframe()["gini"]


print(gini_series(7).equals(gini_series(7)), gini_series(7).equals(gini_series(8)))
```

</details>

**2.2** Replace `self.rng.standard_normal(...)` in a copy of the model by
`numpy.random.standard_normal(...)`. Run `modelly lint` on the copy. What does it report,
and why does it matter?

<details>
<summary>Solution</summary>

`MDL001 random draw outside the model's generators`. The global numpy generator is not
seeded by the scenario, so two runs with the same seed differ, and runs in worker processes
may even share a stream.

</details>

**2.3** Plot the Gini of the Boltzmann exchange over time. How many steps does it take to
settle? Estimate its stationary mean from the second half only, and compare with
`model.stationary_gini()`.

<details>
<summary>Solution</summary>

```python
from modelly.zoo.kinetic_wealth.model import KineticScenario, KineticWealth

model = KineticWealth(KineticScenario(rng=3, steps=1000))
model.run()
series = model.datacollector.get_model_vars_dataframe().iloc[:, 0]
series.plot()
print(series.iloc[500:].mean(), model.stationary_gini())
```

The Gini rises for a few hundred steps, then fluctuates around the exact value.

</details>

**2.4** Save the Bouchaud-Mezard model halfway with `model.save(path)`, load it with
`BouchaudMezard.load(path)` and run both to the end. Are the final wealth vectors equal?

<details>
<summary>Solution</summary>

Yes, element for element: a checkpoint holds the state of both generators, so the resumed
run draws exactly the same numbers. See [Checkpoints](../checkpoints.md).

</details>
