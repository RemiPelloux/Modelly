"""Gradient-based calibration of a :class:`~modelly.diff.model.DiffModel`.

The parameters, the targets and the result read like the other methods of
``modelly.calibrate``: priors give the search box (their support, log-scaled
priors on a log scale), targets give the observed series or statistics::

    fit = GradientCalibration(
        model,
        priors={"innovation": Prior.uniform(0.001, 0.2), "imitation": Prior.uniform(0.05, 1)},
        targets=[Target("adoption", observed=curve)],
        options=GradientOptions(steps=100, iterations=300, seed=1),
    ).run()
    fit.params, fit.gradient   # the estimate and the local sensitivities there

The optimiser is Adam on unconstrained coordinates (a logistic map onto the
box), started at the prior medians. Every iteration runs the same replicate
seeds (common random numbers), so the objective is a deterministic function of
the parameters and the whole fit is the same for the same seed. Replicates are
averaged before the distance, as in the other methods. Score-function draws
add the surrogate ``L + stop_gradient(L) * (log P - stop_gradient(log P))``,
whose gradient is the score-function estimate and whose value is ``L``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from modelly.calibrate import distance
from modelly.calibrate.optimize import UnitBox
from modelly.calibrate.priors import Prior
from modelly.calibrate.targets import Target
from modelly.diff._jax import jax, jnp
from modelly.diff.model import DiffModel

LOSS = "loss"
BETA1, BETA2, EPSILON = 0.9, 0.999, 1e-8  # Adam's defaults (Kingma and Ba 2015)
UNIT_CLIP = 1e-6  # keeps the start strictly inside the box (finite logits)


def _rmse(simulated: Any, observed: Any) -> Any:
    return jnp.sqrt(jnp.mean((simulated - observed) ** 2))


def _mae(simulated: Any, observed: Any) -> Any:
    return jnp.mean(jnp.abs(simulated - observed))


def _euclidean(simulated: Any, observed: Any) -> Any:
    return jnp.sqrt(jnp.sum((simulated - observed) ** 2))


# The built-in distances of modelly.calibrate, written in jax.numpy.
TRACEABLE = {distance.rmse: _rmse, distance.mae: _mae, distance.euclidean: _euclidean}


@dataclass(frozen=True)
class GradientOptions:
    """How the fit runs.

    Attributes:
        steps: steps per simulated run.
        iterations: optimiser iterations.
        learning_rate: Adam's step size, in unconstrained coordinates.
        replicates: runs per evaluation, averaged before the distance.
        seed: the root of every random number: same seed, same fit.
        fixed: parameters every run takes, not fitted.
    """

    steps: int = 100
    iterations: int = 200
    learning_rate: float = 0.05
    replicates: int = 1
    seed: int = 0
    fixed: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class GradientFit:
    """The result: the estimate, its loss, the gradient there and the path to it.

    Attributes:
        params: the parameters with the lowest loss seen.
        loss: their loss.
        gradient: d loss / d parameter at ``params`` (local sensitivities).
        history: one row per iteration: the parameters and the loss.
    """

    params: dict[str, float]
    loss: float
    gradient: dict[str, float]
    history: pd.DataFrame


class GradientCalibration:
    """Fit the priors' parameters of a DiffModel to targets by gradient descent.

    Args:
        model: the differentiable model.
        priors: ``{parameter: Prior}`` (continuous priors) for every fitted parameter.
        targets: the observed quantities; distances are the built-in ``rmse``,
            ``mae`` or ``euclidean``, or any function written with ``jax.numpy``.
        options: steps, iterations, learning rate, replicates and seed.
    """

    def __init__(
        self,
        model: DiffModel,
        priors: Mapping[str, Prior],
        targets: Sequence[Target],
        options: GradientOptions | None = None,
    ) -> None:
        """Check the definition; nothing runs before ``run``."""
        if not priors or not targets:
            raise ValueError("a calibration needs at least one prior and one target")
        self.model, self.priors, self.targets = model, dict(priors), list(targets)
        self.options = options or GradientOptions()
        missing = [t.name for t in self.targets if t.name not in model.outputs]
        if missing:
            raise ValueError(f"targets {missing} are not outputs of the model")
        for target in self.targets:
            target.check_length(self.options.steps)
        self.box = UnitBox(self.priors)

    def params(self, z: Any) -> dict[str, Any]:
        """The parameters at unconstrained coordinates ``z`` (traceable)."""
        unit = jax.nn.sigmoid(z)
        scaled = jnp.asarray(self.box.low) + unit * jnp.asarray(
            self.box.high - self.box.low
        )
        fitted = {
            name: jnp.exp(scaled[i]) if log else scaled[i]
            for i, (name, log) in enumerate(zip(self.box.names, self.box.logs))
        }
        return {**self.options.fixed, **fitted}

    def _distance(self, target: Target, series: Any) -> Any:
        """One target's weighted distance from the replicate series ``[replicate, step]``."""
        if target.summary is None:
            values = series[:, series.shape[1] - len(target.observed) :]
        else:
            values = jax.vmap(lambda row: jnp.atleast_1d(target.summary(row)))(series)
        measure = TRACEABLE.get(target.distance, target.distance)
        return target.weight * measure(
            values.mean(axis=0), jnp.asarray(target.observed)
        )

    def loss(self, params: Mapping[str, Any]) -> Any:
        """The total distance at ``params`` over the replicates (traceable)."""
        keys = jax.random.split(
            jax.random.key(self.options.seed), self.options.replicates
        )
        traces = [self.model.trace(params, self.options.steps, key) for key in keys]
        total = sum(
            self._distance(t, jnp.stack([trace.outputs[t.name] for trace in traces]))
            for t in self.targets
        )
        score = sum(trace.log_prob for trace in traces)
        stop = jax.lax.stop_gradient
        return total + stop(total) * (score - stop(score))

    def _start(self) -> Any:
        """Unconstrained coordinates of the prior medians."""
        unit = self.box.unit(
            {name: prior.median() for name, prior in self.priors.items()}
        )
        unit = np.clip(unit, UNIT_CLIP, 1 - UNIT_CLIP)
        return jnp.asarray(np.log(unit) - np.log1p(-unit))

    def run(self) -> GradientFit:
        """Run Adam for ``options.iterations`` iterations; the best point seen."""
        value_and_grad = jax.jit(
            jax.value_and_grad(lambda z: self.loss(self.params(z)))
        )
        z = self._start()
        moment, second = jnp.zeros_like(z), jnp.zeros_like(z)
        rows, best = [], (np.inf, z)
        for iteration in range(1, self.options.iterations + 1):
            value, grad = value_and_grad(z)
            rows.append({**self._plain(z), LOSS: float(value)})
            best = min(best, (float(value), z), key=lambda pair: pair[0])
            moment = BETA1 * moment + (1 - BETA1) * grad
            second = BETA2 * second + (1 - BETA2) * grad**2
            step = (
                moment
                / (1 - BETA1**iteration)
                / (jnp.sqrt(second / (1 - BETA2**iteration)) + EPSILON)
            )
            z = z - self.options.learning_rate * step
        return self._fit(best, pd.DataFrame(rows))

    def _plain(self, z: Any) -> dict[str, float]:
        """The fitted parameters at ``z`` as Python floats."""
        params = self.params(z)
        return {name: float(params[name]) for name in self.box.names}

    def _fit(self, best: tuple[float, Any], history: pd.DataFrame) -> GradientFit:
        """The fit at the best point, with the gradient in the parameters themselves."""
        params = self._plain(best[1])
        point = {n: jnp.asarray(v) for n, v in params.items()}
        grads = jax.grad(lambda fitted: self.loss({**self.options.fixed, **fitted}))(
            point
        )
        gradient = {name: float(grads[name]) for name in params}
        return GradientFit(params, best[0], gradient, history)
