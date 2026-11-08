# Session 11: causes, effects, attribution and counterfactuals

**Zoo model:** [Bass diffusion](https://remipelloux.github.io/Modelly/zoo/bass_diffusion.html), and the virus-on-a-network example bundled with Modelly (`modelly.examples.basic.virus_on_network`)

## Goals

- Estimate the effect of an intervention with an interval, on common random numbers, and read `variance_reduction`: how many times fewer runs the pairing needs.
- Find the agents an outcome depends on by intervening on each in turn.
- Ask “what if” of a run that has already happened: continue it from a recorded step with and without a change.

**Before the session:** [Causes and explanations](https://remipelloux.github.io/Modelly/explain.html) and [Time travel](https://remipelloux.github.io/Modelly/timetravel.html).

## Walk-through

The Bass model: households adopt an innovation by advertising (`innovation`) and by imitating the households they know (`imitation`). What does raising imitation from 0.38 to 0.40 do to adoption after 60 steps?

```python
from modelly.decide import model_runner
from modelly.explain import treatment_effect
from modelly.zoo.bass_diffusion.model import BassDiffusion, BassScenario

run = model_runner(
    BassDiffusion,
    {"adoption": lambda model: model.adoption},
    scenario=BassScenario,
    base={"steps": 60},
)
effect = treatment_effect(
    run, {}, {"imitation": 0.40}, "adoption", replicates=20, seed=1
)
print(effect.mean, effect.low, effect.high, effect.variance_reduction)
```

About two percentage points more adoption, with an interval a few tenths of a point wide. `run(params, seed)` is the same function `modelly.decide.compare` uses: build the model, run it, return its outputs. Replicate `r` of the control and of the treated arm get the same seed; the treated arm is also run on independent seeds, and `variance_reduction`, about 50 here, is the ratio of the two variances. Fifty times fewer runs for the same interval, on this model; session 10 showed a model where the ratio is about 1.

An effect is a comparison of two runs that differ only by the cause. Attribution and counterfactuals apply the same idea to one agent and to one moment of one run.

## Exercises

**11.1** Measure the effect of vaccinating 10,000 seniors on the number of people infected in the age-structured SEIR model, with 10 replicates. Why is `variance_reduction` close to 1 here, when it is about 50 for Bass?

Solution

```python
import numpy as np

from modelly.zoo.age_seir.model import AgeSEIR, SEIRScenario

def infected(model):
    return float(np.sum(model.attack_rate() * model.sizes))

run = model_runner(
    AgeSEIR, {"infected": infected}, scenario=SEIRScenario, base={"steps": 300}
)
effect = treatment_effect(
    run, {}, {"vaccinated": (0, 0, 10_000)}, "infected", replicates=10, seed=1
)
print(round(effect.mean), round(effect.variance_reduction, 2))
```

About 7,000 fewer infections, and a ratio near 0.8. Common random numbers only help while both arms use the random numbers the same way. Vaccinating adds a cohort row, which changes the order of the binomial draws from the first step: the two arms are then as good as independent. In Bass every household draws one number per step whatever the parameters, so the arms stay aligned until their adoptions differ. To keep the pairing in your own models, write interventions that leave the number and order of the draws unchanged.

**11.2** In a sixty-person outbreak on a contact network, with one infected person at the start, which person matters most? Use `attribute`, making each person resistant in turn.

Solution

```python
from modelly.examples.basic.virus_on_network.agents import State
from modelly.examples.basic.virus_on_network.model import VirusOnNetwork
from modelly.explain import attribute

def outbreak(seed):
    return VirusOnNetwork(
        num_nodes=60, avg_node_degree=3, initial_outbreak_size=1, rng=seed
    )

def touched(model):
    """People infected or resistant: everybody the virus reached and kept."""
    return sum(agent.state != State.SUSCEPTIBLE for agent in model.agents)

def immunise(model, agent):
    agent.state = State.RESISTANT

found = attribute(
    outbreak, lambda m: list(m.agents), touched, steps=40, seeds=[1], intervene=immunise
)
print(found.table.head(3))
index_case = [a.unique_id for a in outbreak(1).agents if a.state == State.INFECTED]
print(found.top(1), index_case)
```

The index case, by far: making it resistant changes the outcome by 48 people, the next person by 6. `attribute` rebuilds the model from the same seed for every candidate, so each rerun is paired with the baseline. The default intervention removes the agent instead; immunising keeps it in the model, which shifts the random draws that follow less.

**11.3** Record one outbreak for 30 steps. What would have happened if everybody infected at step 3 had been cured then? And at step 10?

Solution

```python
from modelly.explain import counterfactual
from modelly.timetravel import Recorder

def cure(model):
    for agent in model.agents:
        if agent.state == State.INFECTED:
            agent.state = State.RESISTANT

model = outbreak(4)
with Recorder(model, every=1) as recorder:
    model.run_for(30)
print(counterfactual(recorder, 3, cure, 30, touched).mean)
for step in (3, 10):
    effect = counterfactual(recorder, step, cure, 30, touched, branches=8)
    print(step, effect.mean, effect.low, effect.high)
```

At step 3 the cure leaves 28 people untouched who were reached in the recorded run. At step 10 it changes nothing within the interval: by then about fifty people have been reached, and curing makes the infected resistant, which `touched` counts anyway. With one branch the two continuations draw exactly the numbers of the recorded run, so the difference is the cure’s effect in that run; with `branches=8` the pairs are reseeded and the result has an interval.

**11.4** Apply a change that does nothing (`lambda model: None`) at step 3, with four branches. What must the effect and its variance be? Why is this a useful test?

Solution

```python
none = counterfactual(recorder, 3, lambda model: None, 30, touched, branches=4)
print(none.mean, none.paired_variance)  # 0.0 0.0
```

Exactly zero, both: the two members of each pair start from the same state with the same seed, so with no change they run the same numbers to the same end. If they did not, a draw would be leaking from outside the model’s generators (session 2), and every counterfactual of that model would mix the change’s effect with noise. Keep this check in your project’s tests.
