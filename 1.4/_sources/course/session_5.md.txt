# Session 5: thinking in arrays, columns and cohorts

**Zoo models:** [Nagel-Schreckenberg](../zoo/nagel_schreckenberg.md),
[age-structured SEIR](../zoo/age_seir.md)

## Goals

- Store the attributes that are updated in bulk as `Column`s, and update the whole
  population with numpy.
- Know when a phase can be vectorised without changing the model (synchronous updates,
  independent draws), and when it cannot.
- Replace individuals by cohorts when everybody in the same state faces the same
  probabilities.

**Before the session:** [Vectorised step phases](../vectorised_phases.md) and
[Profiling a model](../profile.md).

## Exercises

**5.1** Write the Nagel-Schreckenberg step as a loop over cars (`for car in cars: ...`),
with the same rules, and check it gives the same flow as the zoo model for one seed. Which
order must the loop follow, and why?

<details>
<summary>Solution</summary>

The update is parallel: every car's new speed depends on the gaps *before* anybody moves.
Compute all speeds first in one loop, then move all cars in a second loop. With one loop
that moves each car straight away, the car behind sees a larger gap: a different model. Draw
the dawdle coins in one call, `rng.random(n)`, so both versions consume the same random
numbers and give identical flows.

</details>

**5.2** Profile both versions with `modelly profile` on a road of 100,000 cells. How much
faster is the column version?

<details>
<summary>Solution</summary>

```text
modelly profile my_traffic/model.py:NagelSchreckenberg --steps 100 --param length=100000
```

The column version does a handful of numpy operations per step whatever the number of
cars; the loop pays a Python iteration per car. Expect one to two orders of magnitude.

</details>

**5.3** The SEIR model keeps one cohort row per (age group, state). Print
`model.people.to_dataframe()` after a few steps. How many rows are there, and how many
people?

<details>
<summary>Solution</summary>

```python
from modelly.zoo.age_seir.model import AgeSEIR, SEIRScenario

model = AgeSEIR(SEIRScenario(rng=1))
model.run(30)
print(model.people.to_dataframe())
```

At most 12 rows (3 groups x 4 states) after `merge()`, for 100,000 people.

</details>

**5.4** Why would cohorts stop being exact if every person had their own infectiousness?

<details>
<summary>Solution</summary>

A cohort replaces `n` independent draws with the same probability by one binomial draw. If
the probabilities differ within a row, the row is not homogeneous and the binomial has the
wrong law. Either key the cohorts on the trait too (one row per infectiousness class) or
keep individuals.

</details>
