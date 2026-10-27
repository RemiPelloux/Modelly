# Differentiable models

`modelly.diff` computes gradients of a model's outputs with respect to its parameters, through
JAX: for gradient-based calibration, and for local sensitivities (the gradient at a calibrated
point). It works where the model allows it, and this page is mostly about where that is.

```bash
pip install "modelly-abm[diff]"      # JAX on the CPU, on Windows, macOS and Linux
pip install "jax[cuda13]"            # and for an NVIDIA GPU (Linux, Windows)
```

`import modelly.diff` does not import JAX; the first simulated run does. The tests that need
JAX skip without it.

## A model as phases

A `DiffModel` is the array side of a column model: a state (a dict of arrays), an `init`, and
step phases that return the entries they change. JAX traces the phases, runs the steps with
`lax.scan` and differentiates what `outputs` records each step.

```python
import jax
import jax.numpy as jnp

from modelly.diff import DiffModel, check_gradients, phase

N, DT = 2000, 0.01


def init(params, rng):
    return {"wealth": jnp.ones(N), "rich": jnp.zeros(())}


@phase
def returns(state, params, rng):
    sigma = params["volatility"]
    w = state["wealth"] * jnp.exp(sigma * jnp.sqrt(DT) * rng.normal((N,)) - sigma**2 * DT / 2)
    return {"wealth": w / w.mean()}


@phase(differentiable=False)
def census(state, params, rng):
    return {"rich": (state["wealth"] > 2).mean()}


model = DiffModel(init, [returns, census], outputs={"top": lambda s, p: s["wealth"].max()})
series = model.simulate({"volatility": 1.0}, steps=100, seed=1)
grad = jax.grad(lambda p: model.simulate(p, 100, 1)["top"][-1])({"volatility": 1.0})
```

- `rng.normal` and `rng.uniform` are **pathwise** draws: for a fixed seed the run is a smooth
  function of the parameters wherever the phases are smooth, and the gradient is exact.
- `differentiable=False` stops gradients at the phase's updates and makes its Bernoulli draws
  plain 0/1 draws. Use it for bookkeeping, integer counters and rules the gradient should not
  see.
- A phase may change the state's entries but not add new ones: declare every entry in `init`.

Two zoo models ship a differentiable twin: `modelly.zoo.bouchaud_mezard.differentiable`
(wealth condensation, pathwise) and `modelly.zoo.bass_diffusion.differentiable` (well-mixed
Bass diffusion, discrete adoption).

## Discrete choices: estimators, all approximations

An agent that adopts, dies or infects with probability `p` makes a 0/1 choice. For fixed random
numbers the output is a step function of `p`: its derivative is zero almost everywhere and
undefined at the jumps. `rng.bernoulli(p)` in a differentiable phase therefore goes through an
estimator, chosen per model (`DiffModel(..., estimator=...)`) or per draw, and **warns with
`GradientApproximationWarning`** every time, because the result is not the gradient of the
model:

| Estimator | Forward run | Gradient | Use it for |
|---|---|---|---|
| `straight_through` (default) | the exact 0/1 model | biased: each draw differentiated as if it were `p` | calibration, when the direction matters more than the value |
| `gumbel_softmax` | a relaxed model: draws in (0, 1), temperature 0.5 | exact for the relaxed model, not the 0/1 one | sensitivities of a smooth surrogate; gradient checks |
| `score_function` | the exact 0/1 model | unbiased for the expected output, high variance | expectations over many replicates |

With the score function, `GradientCalibration` adds the surrogate
`L + stop_gradient(L) * (log P - stop_gradient(log P))`, whose value is the loss and whose
gradient is the REINFORCE estimate.

## When gradients are meaningful, and when they are not

Meaningful:

- **Continuous state with pathwise noise**: returns, growth, diffusion, opinion averaging
  without thresholds. The gradient is exact for each seed and agrees with finite differences
  (`tests/diff/test_model.py`, Bouchaud-Mezard: relative error below 1e-4).
- **Many independent discrete choices whose aggregate matters**: thousands of households
  adopting, where the adoption curve is a smooth function of the parameters in expectation.
  The straight-through gradient is biased, but it points downhill: the Bass fit below recovers
  both parameters.
- **Local sensitivities at a calibrated point**, read as "how fast the loss changes", with the
  estimator's caveat when a discrete choice is involved.

Not meaningful:

- **Thresholds and hard rules on continuous state** (bounded confidence: "listen only to
  opinions within `epsilon`"; "move when unhappy"): the output is piecewise constant in the
  threshold, the gradient is zero, and no estimator here changes that. Smooth the rule (a
  sigmoid of the distance) in a separate differentiable phase, knowing it is another model.
- **Rare events**: a gradient through a handful of draws (an outbreak that starts or not) is
  dominated by the estimator's bias or variance.
- **Order-dependent sequential updates**, sorting and argmax choices: they change discretely.
- **Integer outputs** (a count of agents) through a non-differentiable phase: zero by design.

`check_gradients(f, params)` compares `jax.grad(f)` with central finite differences in
float64. It passes for pathwise and relaxed models and fails, as it should, through
straight-through or score-function draws, where finite differences of a step function are zero
or huge.

## Gradient-based calibration

`GradientCalibration` takes the priors and targets of [Calibration](calibration.md) and runs
Adam on unconstrained coordinates (a logistic map onto the priors' box, log-scaled priors on a
log scale), from the prior medians. Every iteration runs the same replicate seeds (common
random numbers), so the objective is a deterministic function of the parameters and the fit is
the same for the same seed.

```python
from modelly.calibrate import Prior, Target
from modelly.diff import GradientCalibration, GradientOptions
from modelly.zoo.bass_diffusion.differentiable import differentiable_model

fit = GradientCalibration(
    differentiable_model(households=20_000),
    priors={"innovation": Prior.log_uniform(0.001, 0.3), "imitation": Prior.uniform(0.05, 1.0)},
    targets=[Target("adoption", observed=curve)],
    options=GradientOptions(steps=100, iterations=150, learning_rate=0.05, seed=1),
).run()
fit.params      # the estimate
fit.gradient    # d loss / d parameter there: local sensitivities
fit.history     # parameters and loss per iteration
```

Distances are the built-in `rmse`, `mae` and `euclidean` (traced in JAX) or any function
written with `jax.numpy`; summaries must be written with `jax.numpy` too.

What the tests check (`tests/diff/test_calibrate.py`), each against a run of the agent-based
zoo model at known parameters:

| Zoo model | Gradient | Truth | Recovered | Run |
|---|---|---|---|---|
| Bass diffusion, 20,000 households, 100 steps | straight-through | innovation 0.03, imitation 0.38 | 0.0305, 0.379 (within 2%) | 150 iterations, about 5 s on a laptop CPU |
| Bouchaud-Mezard, 1,000 agents, 300 steps, 2 replicates | pathwise (exact) | volatility 1.5, exchange 1.0 | 1.448, 0.937 (within 7%) | 120 iterations, about 15 s |

The Bouchaud-Mezard estimate is limited by the noise of the observed Gini series (two runs of
1,000 agents), not by the gradient: with four replicates the same fit gives 1.54 and 1.09.
