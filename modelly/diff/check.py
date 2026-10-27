"""Gradient checks: automatic derivatives against central finite differences.

``check_gradients(f, params)`` compares ``jax.grad(f)`` at ``params`` with
``(f(p + h) - f(p - h)) / 2h`` for each parameter, in float64 (inside
``jax.enable_x64``), with ``h`` relative to the parameter's size. They agree
when ``f`` is smooth: a model whose randomness is pathwise (normals, uniforms
through smooth functions) or relaxed (``gumbel_softmax``) with the random
numbers fixed by a seed. They do not agree, and should not, through a
straight-through or score-function estimator: there ``f`` is a step function
for fixed random numbers and its finite differences are zero or huge.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from modelly.diff._jax import jax

DEFAULT_STEP = 1e-5
DEFAULT_TOLERANCE = 1e-4
ABSOLUTE_FLOOR = 1e-10  # below this both derivatives count as zero


@dataclass(frozen=True)
class GradientCheck:
    """Automatic and finite-difference derivatives, parameter by parameter.

    Attributes:
        autodiff: ``{name: df/dname}`` from ``jax.grad``.
        finite_difference: ``{name: central difference}``.
        relative_error: ``{name: |a - f| / max(|a|, |f|)}`` (0 when both are tiny).
        tolerance: the largest relative error accepted.
    """

    autodiff: dict[str, float]
    finite_difference: dict[str, float]
    relative_error: dict[str, float]
    tolerance: float

    @property
    def ok(self) -> bool:
        """Whether every parameter's relative error is within the tolerance."""
        return all(error <= self.tolerance for error in self.relative_error.values())


def _relative(a: float, b: float) -> float:
    """``|a - b| / max(|a|, |b|)``, or 0 when both are below the floor."""
    scale = max(abs(a), abs(b))
    return 0.0 if scale < ABSOLUTE_FLOOR else abs(a - b) / scale


def check_gradients(
    function: Callable[[Mapping[str, float]], float],
    params: Mapping[str, float],
    step: float = DEFAULT_STEP,
    tolerance: float = DEFAULT_TOLERANCE,
) -> GradientCheck:
    """Compare ``jax.grad(function)`` with central differences at ``params``, in float64."""
    with jax.enable_x64(True):
        point = {name: float(value) for name, value in params.items()}
        grads = jax.grad(function)(point)
        autodiff = {name: float(grads[name]) for name in point}
        finite = {}
        for name, value in point.items():
            h = step * max(1.0, abs(value))
            up = float(function({**point, name: value + h}))
            down = float(function({**point, name: value - h}))
            finite[name] = (up - down) / (2 * h)
    errors = {name: _relative(autodiff[name], finite[name]) for name in point}
    return GradientCheck(autodiff, finite, errors, tolerance)
