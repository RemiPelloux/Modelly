"""The Bouchaud-Mezard model as a differentiable model (``modelly.diff``).

The same step as ``model.py``: a multiplicative random return
``W_i <- W_i exp(sigma sqrt(dt) xi_i - sigma^2 dt / 2)``, an exchange toward the
mean at rate ``J``, and a division by the mean, with the Gini coefficient
recorded every step. The returns are pathwise (``xi_i`` standard normal times a
smooth function of ``sigma``), so for fixed random numbers the Gini series is
a smooth function of ``volatility`` and ``exchange`` and its gradient is
exact: it agrees with finite differences, and gradient descent on it fits
both parameters to a Gini series of the agent model.

    model = differentiable_model(n=2000, dt=0.01)
    series = model.simulate({"volatility": 1.0, "exchange": 1.0}, steps=300, seed=1)
"""

from __future__ import annotations

from typing import Any

from modelly.diff._jax import jnp
from modelly.diff.model import DiffModel, phase

HALF = 0.5


def gini(wealth: Any) -> Any:
    """The Gini coefficient ``sum_i (2 i - n - 1) x_(i) / (n sum x)``, in JAX."""
    x = jnp.sort(wealth)
    n = x.shape[0]
    ranks = jnp.arange(1, n + 1)
    return jnp.sum((2 * ranks - n - 1) * x) / (n * jnp.sum(x))


def differentiable_model(n: int = 2000, dt: float = 0.01) -> DiffModel:
    """``n`` savers stepped by ``dt``; parameters ``volatility`` and ``exchange``."""

    def init(params: Any, rng: Any) -> dict[str, Any]:
        return {"wealth": jnp.ones(n)}

    @phase
    def returns_and_exchange(state: dict, params: Any, rng: Any) -> dict[str, Any]:
        sigma, rate = params["volatility"], params["exchange"]
        w = state["wealth"] * jnp.exp(
            sigma * jnp.sqrt(dt) * rng.normal((n,)) - HALF * sigma**2 * dt
        )
        w = w + rate * dt * (w.mean() - w)
        return {"wealth": w / w.mean()}

    return DiffModel(
        init, [returns_and_exchange], {"gini": lambda s, p: gini(s["wealth"])}
    )
