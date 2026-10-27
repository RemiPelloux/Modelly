"""The well-mixed Bass diffusion model as a differentiable model (``modelly.diff``).

The same step as ``model.py`` with ``mixing="well-mixed"``: every household
that has not adopted adopts with probability ``(innovation + imitation *
share) * dt``, ``share`` the adopted share of the population. Adoption is a
0/1 choice, so its gradient needs an estimator (``modelly.diff.estimators``):

* ``"straight_through"`` (the default): the run is the exact agent model; the
  gradient differentiates each draw as if it were its probability, which is
  biased but points the right way, enough to fit ``innovation`` and
  ``imitation`` to an adoption curve;
* ``"gumbel_softmax"``: each household holds a relaxed adoption in (0, 1); the
  gradient is exact for that relaxed model (and agrees with finite
  differences), whose curve is close to, not equal to, the agent model's;
* ``"score_function"``: unbiased for the expected curve, very noisy with
  thousands of households.

Every use warns with ``GradientApproximationWarning``.
"""

from __future__ import annotations

from typing import Any

from modelly.diff._jax import jnp
from modelly.diff.estimators import STRAIGHT_THROUGH
from modelly.diff.model import DiffModel, phase


def differentiable_model(
    households: int = 5000, dt: float = 0.1, estimator: str = STRAIGHT_THROUGH
) -> DiffModel:
    """``households`` well-mixed households; parameters ``innovation`` and ``imitation``."""

    def init(params: Any, rng: Any) -> dict[str, Any]:
        return {"adopted": jnp.zeros(households)}

    @phase
    def adopt(state: dict, params: Any, rng: Any) -> dict[str, Any]:
        adopted = state["adopted"]
        share = adopted.mean()
        hazard = (params["innovation"] + params["imitation"] * share) * dt
        new = rng.bernoulli(jnp.broadcast_to(jnp.minimum(hazard, 1.0), adopted.shape))
        return {"adopted": adopted + (1 - adopted) * new}

    outputs = {"adoption": lambda state, params: state["adopted"].mean()}
    return DiffModel(init, [adopt], outputs, estimator)
