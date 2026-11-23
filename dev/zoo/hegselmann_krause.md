# Hegselmann-Krause bounded-confidence opinion dynamics

**Field:** sociology · **Zoo name:** `hegselmann_krause` · **Module:** `modelly.zoo.hegselmann_krause.model`

![Final clusters against the confidence bound](https://remipelloux.github.io/Modelly/dev/_images/hegselmann_krause.png)

Every agent holds an opinion in `[0, 1]`. At each step, all at once, every agent moves to the mean opinion of the agents within `epsilon` of its own, itself included. Agents further apart never influence each other, so the population splits into clusters that stop moving after a finite number of steps; a wide bound ends in consensus.

## How it is written

Opinions are a `Column` of the `Voter` agents. The confidence set of an agent is a contiguous range of the sorted opinions: two `searchsorted` calls find its ends and a running sum gives its mean, so a step costs `O(n log n)` instead of the `O(n^2)` of comparing every pair (`confidence_means`). The run stops, with `running` set to `False`, as soon as no opinion moves by more than `tolerance`.

```python
from modelly.zoo.hegselmann_krause.model import HegselmannKrause, HKScenario

model = HegselmannKrause(HKScenario(rng=42, epsilon=0.1))
model.run()
model.n_clusters(), model.time  # clusters, and the step at which they froze
```

Parameter

Default

Meaning

n

300

number of agents

epsilon

0.15

confidence bound

tolerance

1e-9

the run stops when no opinion moves more than this

min_cluster_share

0.02

clusters smaller than this share are not counted

steps

100

maximum run length of run()

## Validation

`tests/zoo/test_hegselmann_krause.py` checks, with three seeds, that `epsilon = 0.3` settles into consensus, that `epsilon = 0.05` and `0.1` leave more than two and at most `1 / (2 epsilon)` clusters, and that the mean cluster count falls to one over the sweep `0.05, 0.1, 0.2, 0.3`. The fast step is compared with the plain `O(n^2)` definition on 200 agents over five steps, to within rounding (`1e-12`). A zero bound stops the run after one step, and the same seed gives the same run.

## Model card: Hegselmann-Krause bounded-confidence opinion dynamics

Every agent moves, all at once, to the mean opinion of those within its confidence bound; the population freezes into clusters after finitely many steps, one cluster for a wide bound. A step costs O(n log n).

**Model:** `modelly.zoo.hegselmann_krause.model:HegselmannKrause` · **Validated:** 2026-11-03 with Modelly 1.4.3, on source `8108742edfb2`

### Intended use

- Teaching bounded confidence with synchronous averaging: how the confidence bound decides between consensus and frozen clusters.
- Exploring how the number of opinion clusters falls as the confidence bound grows.
- A starting point for opinion-dynamics models, with a validated core to extend (networks, stubborn agents, heterogeneous bounds).

### Out-of-scope use

- Predicting real opinions, votes or polarisation: opinions are one abstract number and nothing is calibrated to survey data.
- Designing interventions on a real population (moderation, messaging): the model has no media, networks or identities.

### Data

- None by default: initial opinions are drawn uniformly on [0, 1], and the bound and other parameters are illustrative values in `HKScenario`.

### Validation

Check

Test

epsilon = 0.3 settles into a single cluster and the run stops (three seeds)

tests/zoo/test_hegselmann_krause.py::test_wide_bound_reaches_consensus

epsilon = 0.05 and 0.1 leave more than two and at most 1 / (2 epsilon) clusters (three seeds)

tests/zoo/test_hegselmann_krause.py::test_narrow_bound_leaves_several_clusters

the O(n log n) step matches the O(n^2) definition to 1e-12 on 200 agents over five steps

tests/zoo/test_hegselmann_krause.py::test_step_matches_the_quadratic_definition

mean cluster count non-increasing over epsilon = 0.05, 0.1, 0.2, 0.3 and one at 0.3; a zero bound stops after one step; same seed, same run

tests/zoo/test_hegselmann_krause.py

### Known limits

- Every agent hears every other agent within the bound: no social network, and everybody updates at the same time.
- All agents share the same confidence bound; the dynamics are deterministic once the initial opinions are drawn.
- The run stops when no opinion moves by more than `tolerance`, or after `steps` steps.
- Cluster counts depend on how clusters are measured (a gap of half the bound, and clusters under `min_cluster_share` of the agents not counted).

### Ethical considerations

- Results can be read as saying that people with distant views cannot be reached; present them as a property of this stylised rule, not of a real population.

## References

- Hegselmann, R. and Krause, U. (2002). Opinion dynamics and bounded confidence: models, analysis and simulation. *Journal of Artificial Societies and Social Simulation*, 5(3).

Start a project from it with `modelly zoo copy hegselmann_krause my_opinions`.
