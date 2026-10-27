"""Differentiable models: gradients of outputs with respect to parameters, through JAX.

* :class:`DiffModel` and :func:`phase`: column phases over a state of arrays,
  traced and compiled by JAX, with a ``differentiable`` flag per phase;
* :class:`DiffRandom` and the estimators of ``modelly.diff.estimators``:
  pathwise normal and uniform draws, and Bernoulli choices through
  straight-through, Gumbel-softmax or score-function gradients, which warn
  (:class:`GradientApproximationWarning`) because they are approximations;
* :func:`check_gradients`: automatic derivatives against finite differences;
* :class:`GradientCalibration`: Adam on the targets of ``modelly.calibrate``.

``pip install "modelly-abm[diff]"`` installs JAX (CPU on every OS; add the
CUDA plugin, or ``jax-metal`` on macOS, for a GPU). ``import modelly.diff``
does not import JAX; the first traced call does. See ``docs/differentiable.md``.
"""

from modelly.diff.calibrate import GradientCalibration, GradientFit, GradientOptions
from modelly.diff.check import GradientCheck, check_gradients
from modelly.diff.estimators import (
    GUMBEL_SOFTMAX,
    SCORE_FUNCTION,
    STRAIGHT_THROUGH,
    DiffRandom,
    GradientApproximationWarning,
)
from modelly.diff.model import DiffModel, Phase, Trace, phase

__all__ = [
    "GUMBEL_SOFTMAX",
    "SCORE_FUNCTION",
    "STRAIGHT_THROUGH",
    "DiffModel",
    "DiffRandom",
    "GradientApproximationWarning",
    "GradientCalibration",
    "GradientCheck",
    "GradientFit",
    "GradientOptions",
    "Phase",
    "Trace",
    "check_gradients",
    "phase",
]
