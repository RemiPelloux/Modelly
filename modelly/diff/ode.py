"""ODEs in a differentiable model: gradients of ODE parameters, for gradient calibration.

``ode_phase(rhs, state)`` is a ``DiffModel`` phase that integrates ``dy/dt = rhs(t, y,
params)`` over one step for every agent, the state variables being columns of the model's
state, with the classical fourth-order Runge-Kutta method on ``substeps`` equal steps, run by
``lax.scan``. JAX differentiates through those steps, so the gradient is the exact gradient
of the computed solution (discretise, then differentiate) and ``check_gradients`` and
``GradientCalibration`` work on ODE parameters as on any other: a viral clearance rate or a
growth rate is fitted to observed curves by gradient descent. No package beyond JAX (the
``diff`` extra) is needed.

Why not an adaptive solver with an adjoint (``jax.experimental.ode.odeint``): its adjoint
rebuilds the state by integrating backwards in time, which is unstable for any system that
decays (a virus being cleared, a population dying out), and its gradients then blow up. A
fixed step is stable both ways; check the accuracy by halving it (``substeps``), and use
``modelly.couple.solve_batch`` (adaptive, per agent, no gradients) in an ordinary model.

    from modelly.diff import DiffModel
    from modelly.diff.ode import ode_phase

    def decay(t, y, params):
        return -params["clearance"] * y

    model = DiffModel(init, [ode_phase(decay, ["virus"])], outputs={"load": mean_virus})
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from modelly.diff._jax import jnp
from modelly.diff.model import Phase

DEFAULT_SUBSTEPS = 64


def integrate(
    rhs: Callable[[Any, Any, Mapping[str, Any]], Any],
    y0: Any,
    duration: float,
    params: Mapping[str, Any],
    substeps: int = DEFAULT_SUBSTEPS,
    start: Any = 0.0,
) -> Any:
    """The state after ``duration`` by RK4 on ``substeps`` steps (traceable, differentiable).

    ``start`` is the time of the first step, as ``rhs`` sees it.
    """
    from modelly.diff._jax import jax  # noqa: PLC0415 - JAX loads on first use

    h = duration / substeps

    def step(y: Any, t: Any) -> tuple[Any, None]:
        k1 = rhs(t, y, params)
        k2 = rhs(t + h / 2, y + h / 2 * k1, params)
        k3 = rhs(t + h / 2, y + h / 2 * k2, params)
        k4 = rhs(t + h, y + h * k3, params)
        return y + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4), None

    times = start + h * jnp.arange(substeps)
    return jax.lax.scan(step, y0, times)[0]


def ode_phase(
    rhs: Callable[[Any, Any, Mapping[str, Any]], Any],
    state: Sequence[str],
    duration: float = 1.0,
    *,
    substeps: int = DEFAULT_SUBSTEPS,
    name: str | None = None,
) -> Phase:
    """A differentiable phase integrating ``rhs`` over ``duration`` for the columns ``state``.

    ``rhs(t, y, params)`` receives ``y`` of shape ``(len(state), agents)`` and the model's
    parameters; it is written with ``jax.numpy``.
    """
    names = tuple(state)

    def step(columns: Mapping[str, Any], params: Mapping[str, Any], rng: Any) -> dict:
        y0 = jnp.stack([jnp.asarray(columns[n], dtype=float) for n in names])
        y1 = integrate(rhs, y0, duration, params, substeps)
        return {n: y1[i] for i, n in enumerate(names)}

    step.__name__ = name or f"ode_{getattr(rhs, '__name__', 'rhs')}"
    return Phase(step, True, step.__name__)
