"""ABC rejection: sample the priors, run every sample, keep the closest.

The simplest approximate Bayesian computation: ``budget`` parameter points are
drawn from the priors (stream ``(PROPOSAL, REJECTION_KEY)`` of the seed), run
as one batch on the chosen executor, and kept when their distance is within
``tolerance``, or, without a tolerance, when they are among the ``quantile``
closest. The accepted samples have equal weights.

Example:
    >>> calibration = ABCRejection(Epidemic, priors, targets, steps=60, seed=1)  # doctest: +SKIP
    >>> posterior = calibration.run(budget=2000, quantile=0.05)  # doctest: +SKIP
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from modelly.calibrate.base import Calibration, CalibrationError
from modelly.calibrate.posterior import Posterior
from modelly.calibrate.simulator import (
    DEFAULT_EXECUTOR,
    Batch,
    Execution,
    Stream,
    generator,
)

DEFAULT_BUDGET = 1000
DEFAULT_QUANTILE = 0.1
REJECTION_KEY = 2  # first element of the batch key of this method


class ABCRejection(Calibration):
    """ABC rejection sampling over the priors (see the module docstring)."""

    method = "abc-rejection"

    def run(
        self,
        budget: int = DEFAULT_BUDGET,
        quantile: float | None = DEFAULT_QUANTILE,
        tolerance: float | None = None,
        executor: Any = DEFAULT_EXECUTOR,
        **options: Any,
    ) -> Posterior:
        """Run ``budget`` prior samples and keep the closest (``max_parallel`` in options).

        ``tolerance`` keeps every sample within it; otherwise ``quantile`` keeps
        that share of the samples, the closest first.
        """
        if budget < 1:
            raise ValueError(f"budget must be at least 1, got {budget}")
        max_parallel = options.pop("max_parallel", None)
        rng = generator(self.seed, Stream.PROPOSAL, REJECTION_KEY, budget)
        samples = {n: list(p.sample(rng, budget)) for n, p in self.priors.items()}
        batch = Batch((REJECTION_KEY, budget), self.points(samples))
        distances, summaries = self.evaluate(
            batch, Execution(executor, max_parallel, options)
        )
        keep = self._accepted(distances, quantile, tolerance)
        if not keep.size:
            raise CalibrationError(f"no sample within tolerance {tolerance}")
        chosen = {n: [values[i] for i in keep] for n, values in samples.items()}
        weights = np.full(keep.size, 1.0 / keep.size)
        kept = {n: s[keep] for n, s in summaries.items()}
        posterior = self.posterior(chosen, weights, distances[keep], kept)
        accepted = float(distances[keep].max())
        posterior.info = {"runs": budget * self.replicates, "tolerance": accepted}
        posterior.info |= {"acceptance": keep.size / budget}
        return posterior

    @staticmethod
    def _accepted(
        distances: np.ndarray, quantile: float | None, tolerance: float | None
    ) -> np.ndarray:
        """Indices of the accepted samples, in sample order."""
        if tolerance is not None:
            return np.flatnonzero(distances <= tolerance)
        if quantile is None or not 0 < quantile <= 1:
            raise ValueError("give a tolerance, or a quantile in (0, 1]")
        count = max(1, math.floor(quantile * len(distances)))
        order = np.argsort(distances, kind="stable")[:count]
        return np.sort(order)
