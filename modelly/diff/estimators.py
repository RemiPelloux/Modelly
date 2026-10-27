"""Gradients through discrete random choices: three estimators, all approximations.

An agent that adopts, dies or infects with probability ``p`` makes a 0/1
choice; the model's output is a step function of ``p`` for fixed random
numbers, whose derivative is zero almost everywhere. Three standard ways to
get a usable gradient anyway, each with a cost:

* ``"straight_through"`` (Bengio, Leonard and Courville 2013): the forward
  pass draws the exact 0/1 Bernoulli; the backward pass treats the draw as if
  it were ``p`` (derivative one). Exact simulation, **biased** gradient.
* ``"gumbel_softmax"`` (Jang, Gu and Poole 2017; Maddison, Mnih and Teh 2017):
  the draw is replaced by the relaxed Bernoulli
  ``sigmoid((logit p + logistic noise) / temperature)``, a smooth function of
  ``p``. Exact gradient of a **relaxed model** that is not the original one;
  the lower the temperature, the closer the model and the noisier the gradient.
* ``"score_function"`` (REINFORCE, Williams 1992): the draw is exact and
  carries no gradient; the gradient of the expected output comes from
  ``output * d log P(draw) / dp``. **Unbiased** for the expectation, with a
  variance that grows with the number of draws: average many replicates.

Every use warns once with :class:`GradientApproximationWarning`. A pathwise
draw (``normal``, ``uniform`` through a smooth function) needs no estimator:
its gradient is exact for the given random numbers.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any

from modelly.diff._jax import jax, jnp

STRAIGHT_THROUGH = "straight_through"
GUMBEL_SOFTMAX = "gumbel_softmax"
SCORE_FUNCTION = "score_function"
ESTIMATORS = (STRAIGHT_THROUGH, GUMBEL_SOFTMAX, SCORE_FUNCTION)
DEFAULT_TEMPERATURE = 0.5
PROBABILITY_FLOOR = 1e-7  # keeps log p and log(1 - p) finite at p = 0 or 1

APPROXIMATIONS = {
    STRAIGHT_THROUGH: "biased: the 0/1 draw is differentiated as if it were p",
    GUMBEL_SOFTMAX: "exact for a relaxed model (draws in (0, 1)), not for the 0/1 model",
    SCORE_FUNCTION: "unbiased for the expected output, with high variance",
}


class GradientApproximationWarning(UserWarning):
    """A gradient goes through a discrete random choice and is only an approximation."""


def warn_approximation(estimator: str) -> None:
    """Warn that gradients through ``estimator`` are approximate, and how."""
    warnings.warn(
        f"gradient through a discrete choice with {estimator!r}: an approximation "
        f"({APPROXIMATIONS[estimator]}); see docs/differentiable.md",
        GradientApproximationWarning,
        stacklevel=3,
    )


@dataclass
class DiffRandom:
    """The random numbers of one phase in one step, and the log-probability of its draws.

    Attributes:
        key: the JAX key the draws are split from.
        estimator: how ``bernoulli`` passes gradients (see the module docstring).
        differentiable: False in a phase whose updates carry no gradient (exact draws).
        temperature: the Gumbel-softmax temperature.
        log_prob: the sum of log P(draw) of score-function draws, for the surrogate.
    """

    key: Any
    estimator: str = STRAIGHT_THROUGH
    differentiable: bool = True
    temperature: float = DEFAULT_TEMPERATURE
    log_prob: Any = field(default=0.0)

    def _next(self) -> Any:
        """A fresh key for one draw."""
        self.key, key = jax.random.split(self.key)
        return key

    def uniform(self, shape: tuple[int, ...]) -> Any:
        """Uniforms in [0, 1): a pathwise draw, exact gradients through what uses them."""
        return jax.random.uniform(self._next(), shape)

    def normal(self, shape: tuple[int, ...]) -> Any:
        """Standard normals: a pathwise draw (reparameterisation), exact gradients."""
        return jax.random.normal(self._next(), shape)

    def bernoulli(self, p: Any, estimator: str | None = None) -> Any:
        """0/1 draws with probability ``p`` (floats), differentiable by an estimator."""
        estimator = estimator or self.estimator
        if estimator not in ESTIMATORS:
            raise ValueError(
                f"estimator must be one of {ESTIMATORS}, not {estimator!r}"
            )
        p = jnp.clip(p, PROBABILITY_FLOOR, 1 - PROBABILITY_FLOOR)
        u = jax.random.uniform(self._next(), jnp.shape(p))
        hard = (u < p).astype(p.dtype)
        if not self.differentiable:
            return hard
        warn_approximation(estimator)
        if estimator == STRAIGHT_THROUGH:
            return hard + (p - jax.lax.stop_gradient(p))  # forward: exactly hard
        if estimator == GUMBEL_SOFTMAX:
            u = jnp.clip(u, PROBABILITY_FLOOR, 1 - PROBABILITY_FLOOR)
            noise = jnp.log(u) - jnp.log1p(-u)
            logits = jnp.log(p) - jnp.log1p(-p)
            return jax.nn.sigmoid((logits + noise) / self.temperature)
        self.log_prob = self.log_prob + jnp.sum(
            hard * jnp.log(p) + (1 - hard) * jnp.log1p(-p)
        )
        return jax.lax.stop_gradient(hard)
