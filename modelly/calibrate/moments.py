"""The method of simulated moments: match simulated statistics to observed ones.

Each target contributes its observed moments (a series, or the statistics its
``summary`` returns). At a parameter point the replicate mean of the simulated
moments gives the gap ``g = m(theta) - m_observed`` (scaled by the square root
of each target's weight), and the objective is ``g' W g``. ``W`` is the
weighting matrix: the identity, the inverse of the moments' variances
(``"diagonal"``) or of their covariance (``"optimal"``), both estimated from
the replicates at the starting point, or a matrix you give.

The objective is minimised in the priors' unit box with ``scipy.optimize``
(Nelder-Mead or Powell); every evaluation uses the same replicate seeds, so
the search sees a deterministic function.

Example:
    >>> fit = SimulatedMoments(Market, priors, targets, steps=200, replicates=8)  # doctest: +SKIP
    >>> fit.run(evaluations=150).best  # doctest: +SKIP
"""

from __future__ import annotations

from typing import Any

import numpy as np

from modelly.calibrate.optimize import PointEstimate
from modelly.calibrate.posterior import Posterior
from modelly.calibrate.simulator import DEFAULT_EXECUTOR, Execution

DEFAULT_EVALUATIONS = 200
METHODS = ("Nelder-Mead", "Powell")
WEIGHTINGS = ("identity", "diagonal", "optimal")
# Floor of a moment's variance, so a moment that never varies does not dominate.
MIN_VARIANCE = 1e-12


class SimulatedMoments(PointEstimate):
    """Simulated method of moments (see the module docstring).

    Takes the :class:`~modelly.calibrate.base.Calibration` arguments and:

    Args:
        weighting: ``"identity"``, ``"diagonal"``, ``"optimal"`` or a square matrix.
        optimizer: ``"Nelder-Mead"`` or ``"Powell"``.
        start: the starting parameters (default: the prior medians).
    """

    method = "simulated-moments"
    key = 3

    def __init__(
        self,
        *args: Any,
        weighting: str | np.ndarray = "identity",
        optimizer: str = "Nelder-Mead",
        start: dict[str, float] | None = None,
        **kwargs: Any,
    ) -> None:
        """Check the settings; nothing runs before ``run``."""
        super().__init__(*args, **kwargs)
        if optimizer not in METHODS:
            raise ValueError(f"optimizer must be one of {METHODS}, got {optimizer!r}")
        if isinstance(weighting, str) and weighting not in WEIGHTINGS:
            raise ValueError(f"weighting must be a matrix or one of {WEIGHTINGS}")
        if (
            isinstance(weighting, str)
            and weighting != "identity"
            and self.replicates < 2
        ):
            raise ValueError(f"weighting={weighting!r} needs replicates >= 2")
        self.weighting, self.optimizer = weighting, optimizer
        self.start = start or {
            name: prior.median() for name, prior in self.priors.items()
        }
        self.matrix: np.ndarray | None = None

    def moments(self, result: dict[str, np.ndarray]) -> np.ndarray:
        """The scaled gaps of every replicate: ``array[replicate, moment]``."""
        blocks = [
            np.sqrt(t.weight) * (t.replicate_values(result[t.name]) - t.observed)
            for t in self.targets
        ]
        return np.hstack(blocks)

    def _weights(self, gaps: np.ndarray) -> np.ndarray:
        """The weighting matrix, from the replicates' gaps at the starting point."""
        if not isinstance(self.weighting, str):
            matrix = np.asarray(self.weighting, float)
            if matrix.shape != (gaps.shape[1],) * 2:
                raise ValueError(f"the weighting matrix must be {gaps.shape[1]} square")
            return matrix
        if self.weighting == "identity":
            return np.eye(gaps.shape[1])
        if self.weighting == "diagonal":
            return np.diag(1.0 / np.maximum(gaps.var(axis=0, ddof=1), MIN_VARIANCE))
        return np.linalg.pinv(np.atleast_2d(np.cov(gaps, rowvar=False)))

    def objective(self, unit: np.ndarray, execution: Execution) -> float:
        """``g' W g`` at the unit-cube point ``unit`` (the evaluation is recorded)."""
        result = self.simulate([unit], execution)[0]
        gaps = self.moments(result)
        if self.matrix is None:
            self.matrix = self._weights(gaps)
        gap = gaps.mean(axis=0)
        summaries = {t.name: t.simulated(result[t.name]) for t in self.targets}
        return self.record(unit, float(gap @ self.matrix @ gap), summaries)

    def run(
        self,
        evaluations: int = DEFAULT_EVALUATIONS,
        executor: Any = DEFAULT_EXECUTOR,
        max_parallel: int | None = None,
        **options: Any,
    ) -> Posterior:
        """Minimise the objective with at most ``evaluations`` evaluations; the best point."""
        from scipy.optimize import minimize  # noqa: PLC0415 - lazy import

        self.evaluations, self.matrix = [], None
        with Execution(executor, max_parallel, options) as execution:
            found = minimize(
                self.objective,
                self.box.unit(self.start),
                args=(execution,),
                method=self.optimizer,
                bounds=[(0.0, 1.0)] * len(self.names),
                options={"maxfev": evaluations},
            )
        posterior = self.estimate()
        posterior.info |= {
            "success": bool(found.success),
            "message": str(found.message),
        }
        return posterior
