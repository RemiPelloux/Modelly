# Session 6: validation against theory

**Zoo models:** [age-structured SEIR](../zoo/age_seir.md),
[Nagel-Schreckenberg](../zoo/nagel_schreckenberg.md), [Bass diffusion](../zoo/bass_diffusion.md)

## Goals

- Validate a stochastic model against an analytical result, with a tolerance that comes from
  the variance of the estimate and not from trial and error.
- Use a deterministic limit (no noise, infinite population) where the theory is exact.
- Write the check as a test that runs on every change.

**Before the session:** the validation sections of the three zoo pages, and
`tests/zoo/test_age_seir.py`.

## Exercises

**6.1** For a homogeneous population of 100,000 with `R0 = 2`, compute the final size from
`s = exp(-R0 (1 - s))` and compare with the SEIR model for five seeds.

<details>
<summary>Solution</summary>

```python
import numpy as np
from scipy.optimize import brentq

from modelly.zoo.age_seir.model import AgeSEIR, SEIRScenario

expected = 1 - brentq(lambda s: s - np.exp(-2 * (1 - s)), 1e-9, 0.5)
for seed in range(5):
    model = AgeSEIR(
        SEIRScenario(
            rng=seed,
            group_sizes=(100_000,),
            contacts=((10.0,),),
            beta=0.04,
            recovery=0.2,
            initial_infected=(20,),
            steps=800,
        )
    )
    model.run()
    print(round(model.attack_rate()[0], 4), round(expected, 4))
```

</details>

**6.2** The test bounds the error by five standard deviations of the final size. Where does
the standard deviation come from, and why five?

<details>
<summary>Solution</summary>

From the central limit theorem for the final size of an epidemic (Andersson and Britton):
the attack rate is approximately normal around the root of the final-size relation, with a
variance that depends on `R0`, the final size and the variance of the infectious period,
divided by the population. Five standard deviations make a false failure a one-in-a-million
event, and the test uses fixed seeds anyway, so it never flickers; a real bug moves the
result by much more.

</details>

**6.3** With `dawdle=0` the Nagel-Schreckenberg flow is exactly `min(rho * vmax, 1 - rho)`.
Check it at density 0.3, then explain why the check uses densities away from
`1 / (vmax + 1)`.

<details>
<summary>Solution</summary>

```python
from modelly.zoo.nagel_schreckenberg.model import fundamental_diagram

print(fundamental_diagram([0.3], 300, 200, rng=1, dawdle=0.0), min(0.3 * 5, 0.7))
```

At the critical density the transient, before the jams dissolve, is longest; a check there
would need far more steps.

</details>

**6.4** Write a pytest test that fails if the well-mixed Bass model drifts more than four
standard deviations `sqrt(F (1 - F) / N)` from the Bass curve at mid-diffusion.

<details>
<summary>Solution</summary>

```python
import numpy as np

from modelly.zoo.bass_diffusion.model import BassDiffusion, BassScenario, bass_curve


def test_bass_midpoint():
    model = BassDiffusion(BassScenario(rng=1, steps=60))
    model.run()
    frame = model.datacollector.get_model_vars_dataframe()
    expected = bass_curve(frame["time"].to_numpy(), 0.03, 0.38)[-1]
    sd = np.sqrt(expected * (1 - expected) / model.scenario.households)
    assert abs(frame["adoption"].iloc[-1] - expected) < 4 * sd + 0.01  # + Euler error
```

The zoo's own test computes the Euler error of the time step exactly instead of allowing a
fixed 0.01.

</details>
