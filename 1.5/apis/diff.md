# Differentiable models

`modelly.diff` simulates models written as JAX phases and differentiates their outputs with respect to their parameters. How to use it, and when the gradients mean something, is in [Differentiable models](https://remipelloux.github.io/Modelly/differentiable.html).

## Models and phases

A model as JAX column phases: traced, compiled and differentiated with respect to parameters.

A [`DiffModel`](https://remipelloux.github.io/Modelly/apis/diff.html#modelly.diff.model.DiffModel) is the array side of a Modelly model written with columns: a state (a dict of column arrays and model-level values), an `init(params, rng)` that builds it, and step phases that each return the columns they change. JAX traces the phases once, runs the steps with `lax.scan` and differentiates the recorded outputs with respect to `params`:

```default
@phase
def returns(state, params, rng):
    w = state["wealth"] * jnp.exp(params["volatility"] * rng.normal(n))
    return {"wealth": w / w.mean()}

@phase(differentiable=False)
def census(state, params, rng):
    return {"rich": (state["wealth"] > 2).sum()}

model = DiffModel(init, [returns, census], outputs={"gini": gini})
series = model.simulate({"volatility": 0.4}, steps=100, seed=1)
grads = jax.grad(lambda p: model.simulate(p, 100, 1)["gini"][-1])(params)
```

`differentiable=False` stops gradients at the phase’s updates (bookkeeping, integer counters, a rule the gradient should not see) and makes its Bernoulli draws exact 0/1 draws. In a differentiable phase a Bernoulli draw goes through an estimator (`modelly.diff.estimators`), and warns that the gradient is an approximation; normal and uniform draws are pathwise and exact.

#### `class Phase(function: Callable[[dict[str, Any], Mapping[str, Any], DiffRandom], Mapping[str, Any]], differentiable: bool = True, name: str = '')`

One step phase: a function of (state, params, rng) returning updated entries.

**Variables:**

- **function** ([*collections.abc.Callable*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)*[**[*[*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **Any**]**, *[*collections.abc.Mapping*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **Any**]**, *[*modelly.diff.estimators.DiffRandom*](https://remipelloux.github.io/Modelly/apis/diff.html#modelly.diff.estimators.DiffRandom)*]**, *[*collections.abc.Mapping*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **Any**]**]*) – the phase; it returns a dict of the state entries it changes.
- **differentiable** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)) – whether gradients flow through its updates.
- **name** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – the phase’s name (the function’s by default).

#### `phase(function: Callable[[dict[str, Any], Mapping[str, Any], DiffRandom], Mapping[str, Any]] | None = None, *, differentiable: bool = True) → Any`

Declare a step phase, as `@phase` or `@phase(differentiable=False)`.

#### `class Trace(outputs: dict[str, Any], log_prob: Any)`

One simulated run: the output series and the score-function log-probability.

**Variables:**

- **outputs** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, **Any**]*) – `{name: array}`, one value per step, the initial state first.
- **log_prob** (*Any*) – sum of log P(draw) over score-function draws (0 without any).

#### `class DiffModel(init: Callable[[Mapping[str, Any], DiffRandom], dict[str, Any]], phases: Sequence[Phase | Callable[[dict[str, Any], Mapping[str, Any], DiffRandom], Mapping[str, Any]]], outputs: Mapping[str, Callable[[dict[str, Any], Mapping[str, Any]], Any]], estimator: str = 'straight_through')`

Column phases over a state of arrays, simulated and differentiated by JAX.

**Parameters:**

- **init** – `init(params, rng) -> state`, the initial state (a dict of arrays).
- **phases** – the step phases in order (`Phase` objects or plain functions).
- **outputs** – `{name: fn(state, params) -> scalar}`, recorded every step.
- **estimator** – the default estimator of Bernoulli draws (see `estimators`).

Check the phases and the estimator; nothing is traced yet.

#### `record(state: dict[str, Any], params: Mapping[str, Any]) → dict[str, Any]`

The outputs of `state`.

#### `trace(params: Mapping[str, Any], steps: int, key: Any) → Trace`

Simulate `steps` steps from `key` (traceable: use it inside jax.grad).

#### `simulate(params: Mapping[str, Any], steps: int, seed: int = 0) → dict`

The output series of one run seeded with `seed` (JAX arrays).

## Discrete choices

Gradients through discrete random choices: three estimators, all approximations.

An agent that adopts, dies or infects with probability `p` makes a 0/1 choice; the model’s output is a step function of `p` for fixed random numbers, whose derivative is zero almost everywhere. Three standard ways to get a usable gradient anyway, each with a cost:

- `"straight_through"` (Bengio, Leonard and Courville 2013): the forward pass draws the exact 0/1 Bernoulli; the backward pass treats the draw as if it were `p` (derivative one). Exact simulation, **biased** gradient.
- `"gumbel_softmax"` (Jang, Gu and Poole 2017; Maddison, Mnih and Teh 2017): the draw is replaced by the relaxed Bernoulli `sigmoid((logit p + logistic noise) / temperature)`, a smooth function of `p`. Exact gradient of a **relaxed model** that is not the original one; the lower the temperature, the closer the model and the noisier the gradient.
- `"score_function"` (REINFORCE, Williams 1992): the draw is exact and carries no gradient; the gradient of the expected output comes from `output * d log P(draw) / dp`. **Unbiased** for the expectation, with a variance that grows with the number of draws: average many replicates.

Every use warns once with [`GradientApproximationWarning`](https://remipelloux.github.io/Modelly/apis/diff.html#modelly.diff.estimators.GradientApproximationWarning). A pathwise draw (`normal`, `uniform` through a smooth function) needs no estimator: its gradient is exact for the given random numbers.

#### `exception GradientApproximationWarning`

A gradient goes through a discrete random choice and is only an approximation.

#### `warn_approximation(estimator: str) → None`

Warn that gradients through `estimator` are approximate, and how.

#### `class DiffRandom(key: Any, estimator: str = 'straight_through', differentiable: bool = True, temperature: float = 0.5, log_prob: Any = 0.0)`

The random numbers of one phase in one step, and the log-probability of its draws.

**Variables:**

- **key** (*Any*) – the JAX key the draws are split from.
- **estimator** ([*str*](https://docs.python.org/3/builtins/stdtypes.html#str)) – how `bernoulli` passes gradients (see the module docstring).
- **differentiable** ([*bool*](https://docs.python.org/3/builtins/functions.html#bool)) – False in a phase whose updates carry no gradient (exact draws).
- **temperature** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the Gumbel-softmax temperature.
- **log_prob** (*Any*) – the sum of log P(draw) of score-function draws, for the surrogate.

#### `uniform(shape: tuple[int, ...]) → Any`

Uniforms in [0, 1): a pathwise draw, exact gradients through what uses them.

#### `normal(shape: tuple[int, ...]) → Any`

Standard normals: a pathwise draw (reparameterisation), exact gradients.

#### `bernoulli(p: Any, estimator: str | None = None) → Any`

0/1 draws with probability `p` (floats), differentiable by an estimator.

## Gradient checks

Gradient checks: automatic derivatives against central finite differences.

`check_gradients(f, params)` compares `jax.grad(f)` at `params` with `(f(p + h) - f(p - h)) / 2h` for each parameter, in float64 (inside `jax.enable_x64`), with `h` relative to the parameter’s size. They agree when `f` is smooth: a model whose randomness is pathwise (normals, uniforms through smooth functions) or relaxed (`gumbel_softmax`) with the random numbers fixed by a seed. They do not agree, and should not, through a straight-through or score-function estimator: there `f` is a step function for fixed random numbers and its finite differences are zero or huge.

#### `class GradientCheck(autodiff: dict[str, float], finite_difference: dict[str, float], relative_error: dict[str, float], tolerance: float)`

Automatic and finite-difference derivatives, parameter by parameter.

**Variables:**

- **autodiff** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*float*](https://docs.python.org/3/builtins/functions.html#float)*]*) – `{name: df/dname}` from `jax.grad`.
- **finite_difference** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*float*](https://docs.python.org/3/builtins/functions.html#float)*]*) – `{name: central difference}`.
- **relative_error** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*float*](https://docs.python.org/3/builtins/functions.html#float)*]*) – `{name: |a - f| / max(|a|, |f|)}` (0 when both are tiny).
- **tolerance** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – the largest relative error accepted.

#### `property ok: bool`

Whether every parameter’s relative error is within the tolerance.

#### `check_gradients(function: Callable[[Mapping[str, float]], float], params: Mapping[str, float], step: float = 1e-05, tolerance: float = 0.0001) → GradientCheck`

Compare `jax.grad(function)` with central differences at `params`, in float64.

## Gradient-based calibration

Gradient-based calibration of a [`DiffModel`](https://remipelloux.github.io/Modelly/apis/diff.html#modelly.diff.model.DiffModel).

The parameters, the targets and the result read like the other methods of `modelly.calibrate`: priors give the search box (their support, log-scaled priors on a log scale), targets give the observed series or statistics:

```default
fit = GradientCalibration(
    model,
    priors={"innovation": Prior.uniform(0.001, 0.2), "imitation": Prior.uniform(0.05, 1)},
    targets=[Target("adoption", observed=curve)],
    options=GradientOptions(steps=100, iterations=300, seed=1),
).run()
fit.params, fit.gradient   # the estimate and the local sensitivities there
```

The optimiser is Adam on unconstrained coordinates (a logistic map onto the box), started at the prior medians. Every iteration runs the same replicate seeds (common random numbers), so the objective is a deterministic function of the parameters and the whole fit is the same for the same seed. Replicates are averaged before the distance, as in the other methods. Score-function draws add the surrogate `L + stop_gradient(L) * (log P - stop_gradient(log P))`, whose gradient is the score-function estimate and whose value is `L`.

#### `class GradientOptions(steps: int = 100, iterations: int = 200, learning_rate: float = 0.05, replicates: int = 1, seed: int = 0, fixed: Mapping[str, float]=<factory>)`

How the fit runs.

**Variables:**

- **steps** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – steps per simulated run.
- **iterations** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – optimiser iterations.
- **learning_rate** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – Adam’s step size, in unconstrained coordinates.
- **replicates** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – runs per evaluation, averaged before the distance.
- **seed** ([*int*](https://docs.python.org/3/builtins/functions.html#int)) – the root of every random number: same seed, same fit.
- **fixed** ([*collections.abc.Mapping*](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*float*](https://docs.python.org/3/builtins/functions.html#float)*]*) – parameters every run takes, not fitted.

#### `class GradientFit(params: dict[str, float], loss: float, gradient: dict[str, float], history: DataFrame)`

The result: the estimate, its loss, the gradient there and the path to it.

**Variables:**

- **params** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*float*](https://docs.python.org/3/builtins/functions.html#float)*]*) – the parameters with the lowest loss seen.
- **loss** ([*float*](https://docs.python.org/3/builtins/functions.html#float)) – their loss.
- **gradient** ([*dict*](https://docs.python.org/3/builtins/stdtypes.html#dict)*[*[*str*](https://docs.python.org/3/builtins/stdtypes.html#str)*, *[*float*](https://docs.python.org/3/builtins/functions.html#float)*]*) – d loss / d parameter at `params` (local sensitivities).
- **history** (*pandas.DataFrame*) – one row per iteration: the parameters and the loss.

#### `class GradientCalibration(model: DiffModel, priors: Mapping[str, Prior], targets: Sequence[Target], options: GradientOptions | None = None)`

Fit the priors’ parameters of a DiffModel to targets by gradient descent.

**Parameters:**

- **model** – the differentiable model.
- **priors** – `{parameter: Prior}` (continuous priors) for every fitted parameter.
- **targets** – the observed quantities; distances are the built-in `rmse`, `mae` or `euclidean`, or any function written with `jax.numpy`.
- **options** – steps, iterations, learning rate, replicates and seed.

Check the definition; nothing runs before `run`.

#### `params(z: Any) → dict[str, Any]`

The parameters at unconstrained coordinates `z` (traceable).

#### `loss(params: Mapping[str, Any]) → Any`

The total distance at `params` over the replicates (traceable).

#### `run() → GradientFit`

Run Adam for `options.iterations` iterations; the best point seen.

## Zoo twins

The Bouchaud-Mezard model as a differentiable model (`modelly.diff`).

The same step as `model.py`: a multiplicative random return `W_i <- W_i exp(sigma sqrt(dt) xi_i - sigma^2 dt / 2)`, an exchange toward the mean at rate `J`, and a division by the mean, with the Gini coefficient recorded every step. The returns are pathwise (`xi_i` standard normal times a smooth function of `sigma`), so for fixed random numbers the Gini series is a smooth function of `volatility` and `exchange` and its gradient is exact: it agrees with finite differences, and gradient descent on it fits both parameters to a Gini series of the agent model.

model = differentiable_model(n=2000, dt=0.01) series = model.simulate({“volatility”: 1.0, “exchange”: 1.0}, steps=300, seed=1)

#### `gini(wealth: Any) → Any`

The Gini coefficient `sum_i (2 i - n - 1) x_(i) / (n sum x)`, in JAX.

#### `differentiable_model(n: int = 2000, dt: float = 0.01) → DiffModel`

`n` savers stepped by `dt`; parameters `volatility` and `exchange`.

The well-mixed Bass diffusion model as a differentiable model (`modelly.diff`).

The same step as `model.py` with `mixing="well-mixed"`: every household that has not adopted adopts with probability `(innovation + imitation * share) * dt`, `share` the adopted share of the population. Adoption is a 0/1 choice, so its gradient needs an estimator (`modelly.diff.estimators`):

- `"straight_through"` (the default): the run is the exact agent model; the gradient differentiates each draw as if it were its probability, which is biased but points the right way, enough to fit `innovation` and `imitation` to an adoption curve;
- `"gumbel_softmax"`: each household holds a relaxed adoption in (0, 1); the gradient is exact for that relaxed model (and agrees with finite differences), whose curve is close to, not equal to, the agent model’s;
- `"score_function"`: unbiased for the expected curve, very noisy with thousands of households.

Every use warns with `GradientApproximationWarning`.

#### `differentiable_model(households: int = 5000, dt: float = 0.1, estimator: str = 'straight_through') → DiffModel`

`households` well-mixed households; parameters `innovation` and `imitation`.

## ODEs in a differentiable model

ODEs in a differentiable model: gradients of ODE parameters, for gradient calibration.

`ode_phase(rhs, state)` is a `DiffModel` phase that integrates `dy/dt = rhs(t, y, params)` over one step for every agent, the state variables being columns of the model’s state, with the classical fourth-order Runge-Kutta method on `substeps` equal steps, run by `lax.scan`. JAX differentiates through those steps, so the gradient is the exact gradient of the computed solution (discretise, then differentiate) and `check_gradients` and `GradientCalibration` work on ODE parameters as on any other: a viral clearance rate or a growth rate is fitted to observed curves by gradient descent. No package beyond JAX (the `diff` extra) is needed.

Why not an adaptive solver with an adjoint (`jax.experimental.ode.odeint`): its adjoint rebuilds the state by integrating backwards in time, which is unstable for any system that decays (a virus being cleared, a population dying out), and its gradients then blow up. A fixed step is stable both ways; check the accuracy by halving it (`substeps`), and use `modelly.couple.solve_batch` (adaptive, per agent, no gradients) in an ordinary model.

from modelly.diff import DiffModel from modelly.diff.ode import ode_phase

**def decay(t, y, params):**

return -params[“clearance”] * y

model = DiffModel(init, [ode_phase(decay, [“virus”])], outputs={“load”: mean_virus})

#### `integrate(rhs: Callable[[Any, Any, Mapping[str, Any]], Any], y0: Any, duration: float, params: Mapping[str, Any], substeps: int = 64, start: Any = 0.0) → Any`

The state after `duration` by RK4 on `substeps` steps (traceable, differentiable).

`start` is the time of the first step, as `rhs` sees it.

#### `ode_phase(rhs: Callable[[Any, Any, Mapping[str, Any]], Any], state: Sequence[str], duration: float = 1.0, *, substeps: int = 64, name: str | None = None) → Phase`

A differentiable phase integrating `rhs` over `duration` for the columns `state`.

`rhs(t, y, params)` receives `y` of shape `(len(state), agents)` and the model’s parameters; it is written with `jax.numpy`.
