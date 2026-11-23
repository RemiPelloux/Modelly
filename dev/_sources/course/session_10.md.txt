# Session 10: decisions, strategies and costs

**Zoo model:** [age-structured SEIR](../zoo/age_seir.md), through the vaccination study of
`modelly.decide.vaccination`

## Goals

- Compare strategies on common random numbers: every strategy faces the same chance events
  in replicate `r`, so differences are paired.
- Report a ranking with intervals and with how often each strategy was the best, and
  measure what the pairing bought instead of assuming it.
- Place strategies by cost and effect: dominated strategies, the efficient frontier, the
  incremental cost-effectiveness ratio and the net benefit at a willingness to pay.

**Before the session:** [Decisions](../decide.md) and the model card at the end of the
[age-structured SEIR page](../zoo/age_seir.md).

## Walk-through

A town of 100,000 people in three age groups, and 10,000 doses to give before an epidemic:
to the children, the adults, the seniors, or nobody. The study is in
`modelly.decide.vaccination`; read its forty lines first, then run it:

```python
from modelly.decide import cost_effectiveness
from modelly.decide.vaccination import vaccination_study

study = vaccination_study(replicates=10, seed=7)
print(study.rank("deaths"))
print(study.difference("deaths"))
print(cost_effectiveness(study, "deaths_averted"))
```

`rank` orders the strategies by mean deaths, with a 95% interval and `best_share`, the
share of replicates in which each was the best. `difference` subtracts the first strategy,
`nobody`, replicate by replicate. `cost_effectiveness` sorts them by cost: vaccinating the
children is cheaper than giving no doses at all, because each infection costs care and
children drive transmission; the seniors avert the most deaths, at an extra cost of about
9,700 per death averted over the children. `study.runs` holds every run, one row per
strategy and replicate, with its seed.

The same comparison runs without code in Studio's **Compare** tab:
`modelly studio --hub age_seir --no-code`.

## Exercises

**10.1** Run the study with 10 replicates, then with 20 and the same seed. Do the rankings
change? Does the interval of the seniors' deaths shrink as you expect?

<details>
<summary>Solution</summary>

```python
for replicates in (10, 20):
    study = vaccination_study(replicates=replicates, seed=7)
    print(study.rank("deaths"))
```

The order is the same (seniors, adults, children, nobody) and the seniors are best in every
replicate. The interval is a Student-t interval of the mean, so its width falls about as
`1 / sqrt(replicates)`: twice the replicates, about 0.7 times the width. The first ten
replicates are the same in both runs, because the replicate seeds are spawned from one
`SeedSequence(seed)`.

</details>

**10.2** Measure what common random numbers buy in this study: for each strategy against
`nobody`, divide the variance of the difference with independent runs by the variance of
the paired difference. Compare with the Bass diffusion model of
[Causes and explanations](../explain.md).

<details>
<summary>Solution</summary>

```python
import numpy as np

study = vaccination_study(replicates=10, seed=7)
base = study.values("deaths", "nobody")
for name in ("children", "adults", "seniors"):
    other = study.values("deaths", name)
    paired = np.var(other - base, ddof=1)
    unpaired = np.var(other, ddof=1) + np.var(base, ddof=1)
    print(name, round(unpaired / paired, 2))
```

About 1: here the pairing buys almost nothing. Vaccinating a group adds a cohort row to the
SEIR model, which changes the order of the binomial draws from the first step, so the two
arms of a pair soon see different chance events. In the Bass model every household draws
one number per step whatever the parameters, and the ratio is about 50. The intervals of
this study are narrow anyway because 100,000 people average out most of the chance. Measure
the gain on your own model; session 11 does it with `treatment_effect`.

</details>

**10.3** Below which willingness to pay per death averted is vaccinating the children the
best choice by net benefit, and above which is it the seniors? Check at 5,000 and 20,000.

<details>
<summary>Solution</summary>

```python
from modelly.decide import net_benefit

study = vaccination_study(replicates=10, seed=7)
for wtp in (5_000, 20_000):
    print(wtp, net_benefit(study, "deaths_averted", wtp=wtp)[["mean", "best_share"]])
```

The switch is at the ICER of the seniors over the children, about 9,700: below it each extra
death averted costs more than it is worth, and the children win; above it the seniors win.
That is what an ICER is, the willingness to pay at which two frontier strategies have the
same net benefit. Adults are never best: they are extendedly dominated, since a mix of the
children's and the seniors' strategies would avert more deaths for the same money.

</details>

**10.4** Add a strategy of your own: half the doses to the children and half to the seniors.
Write the runner and the costs yourself with `model_runner` and `Strategy`, and compare it
with `nobody` and `seniors`.

<details>
<summary>Solution</summary>

```python
from modelly.decide import Strategy, compare, model_runner
from modelly.decide.vaccination import deaths, infections
from modelly.zoo.age_seir.model import AgeSEIR, SEIRScenario

run = model_runner(
    AgeSEIR,
    {"infections": infections, "deaths": deaths},
    scenario=SEIRScenario,
    base={"steps": 300},
)


def care(doses):
    """20 per dose, 150 per infection."""
    return lambda outputs: 20.0 * doses + 150.0 * outputs["infections"]


strategies = [
    Strategy("nobody", {}, care(0)),
    Strategy("seniors", {"vaccinated": (0, 0, 10_000)}, care(10_000)),
    Strategy("split", {"vaccinated": (5_000, 0, 5_000)}, care(10_000)),
]
study = compare(run, strategies, replicates=10, seed=7)
print(study.rank("deaths"))
print(study.difference("deaths", baseline="seniors"))
print(study.summary("cost"))
```

The split averts fewer deaths than the seniors alone (about 66 more deaths, interval 63 to
69) and costs less (about 10.1 M against 10.8 M): neither dominates the other, so the
choice depends on the willingness to pay, as in 10.3. Use the same `seed` as the other
studies so that a reader can rerun every table.

</details>
