# Causes and explanations

`modelly.explain` says why an outcome happened, not only that it did. It covers:

- the effect of an intervention, with an interval;
- the agents an outcome depends on;
- what a recorded run would have done with one change;
- how much each parameter moved an emulator’s prediction.

```python
from modelly.explain import attribute, counterfactual, shapley, treatment_effect

effect = treatment_effect(
    run, control={}, treated={"imitation": 0.40}, output="adoption"
)
effect.mean, effect.low, effect.high, effect.variance_reduction
```

## Treatment effects and common random numbers

`treatment_effect(run, control, treated, output, replicates=30, seed=0)` runs both arms `replicates` times. Replicate `r` of both arms gets the same seed: **common random numbers**. The two runs of a pair then see the same chance events, so their difference is the effect of the treatment plus far less noise. The `Effect` holds the mean difference and its interval. By default it also measures what the pairing bought. The treated arm is run again on independent seeds, and `variance_reduction` is the variance of the unpaired difference divided by that of the paired one: how many times fewer runs the pairing needs for the same precision. `workers=` runs the replicates over processes with identical results, as in [Decisions](https://remipelloux.github.io/Modelly/dev/decide.html#comparing-strategies); `attribute` takes it too.

On the [Bass diffusion zoo model](https://remipelloux.github.io/Modelly/dev/zoo/bass_diffusion.html), raising imitation from 0.38 to 0.40 adds about 2.05 percentage points of adoption after 60 steps (1.92 to 2.18 for 30 pairs with `seed=0`). Common random numbers reduce the variance of that estimate 24 to 62 times over ten seeds of the study (median 42); for a larger change, to 0.45, 10 to 19 times. The ratio is itself an estimate from 30 pairs, hence the spread. Every household draws one number per step whatever the parameters, so the pairs stay aligned until their adoptions differ.

The pairing only helps while the two arms consume the random numbers the same way. In the [age-structured SEIR model](https://remipelloux.github.io/Modelly/dev/zoo/age_seir.html), vaccinating a group adds a cohort row, which changes the order of the binomial draws from the first step. The two arms are then effectively independent, and the measured ratio is 0.6 to 1.3 over ten seeds, no gain. On the [hospital epidemic](https://remipelloux.github.io/Modelly/dev/zoo/hospital_epidemic.html), the contact response changes when people are infected, and the gain is 1.9 times on the peak occupancy. `variance_reduction` measures this for your model rather than assuming it. To keep the pairing, write interventions that leave the number and order of the draws unchanged: a per-agent [random stream](https://remipelloux.github.io/Modelly/dev/determinism.html) helps.

## Attribution: which agents mattered

`attribute(build, candidates, output, steps=..., seeds=...)` reruns the model once per candidate agent, intervening on that agent at the start, and records how far the outcome moves from the baseline on the same seed:

```python
from modelly.explain import attribute

def immunise(model, agent):
    agent.state = State.RESISTANT

found = attribute(
    lambda seed: VirusOnNetwork(num_nodes=60, initial_outbreak_size=1, rng=seed),
    lambda model: list(model.agents),
    lambda model: sum(a.state != State.SUSCEPTIBLE for a in model.agents),
    steps=40,
    seeds=[1],
    intervene=immunise,
)
found.top(3)  # unique ids, largest effect first
```

The default intervention removes the agent. Effects are kept by unique id and averaged over the seeds, with intervals. In a sixty-person outbreak on a contact network with one index case, immunising the index case moves the outbreak by 45 to 51 infections, depending on the seed. The next agent moves it by 4 to 10. Attribution ranks the index case first for every seed tested (`tests/explain/test_explain.py`).

## Counterfactuals on a recorded run

A run that has already happened can be asked “what if”. `counterfactual` continues it from a recorded step (see [Time travel](https://remipelloux.github.io/Modelly/dev/timetravel.html)) twice: as it was, and with a change applied:

```python
from modelly.timetravel import Recorder

with Recorder(model, every=1) as recorder:
    model.run_for(30)

effect = counterfactual(recorder, 3, cure_everyone, 30, ever_infected, branches=8)
```

With one branch, both continuations draw exactly the numbers of the recorded run, so the difference is the change’s effect in that run. With `branches=n`, pair `i` is reseeded from the run’s own seed, the same seed for both members of the pair, and the result has an interval.

## Shapley values on an emulator

`shapley(predict, point, background, names)` splits an [emulator](https://remipelloux.github.io/Modelly/dev/emulators.html)’s prediction at `point`, minus its mean over a background sample, between the parameters. It computes the values exactly, by enumerating every subset of parameters (`2**d` evaluations, up to 16 parameters); the values add up to the difference:

```python
from modelly.explain import shapley

emulator = GaussianEmulator.from_results(results, space, ["attack"])
predict = emulator.select("attack").predict_unit
shapley(predict, point_in_unit_cube, background_units, names=list(space.dimensions))
```

An emulator makes each of the `2**d` evaluations cheap, so the explanation costs no model runs.
