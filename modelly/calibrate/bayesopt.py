"""Bayesian optimisation of the targets' distance: a basic Gaussian-process search.

A built-in, deliberately small optimiser for models too expensive for ABC:
``initial`` points of a Latin hypercube over the priors' unit box, then, one
point at a time, the candidate with the largest expected improvement under a
Gaussian process (:mod:`modelly.calibrate.gp`) fitted to every evaluation so
far. Candidates are random points of the box from a seeded stream, so a run
is reproducible. It returns the best point found, not a posterior
distribution, and suits a handful of parameters and up to a few hundred
evaluations; no external optimisation library is needed.

Example:
    >>> search = BayesOpt(Epidemic, priors, targets, steps=60, replicates=4, seed=3)  # doctest: +SKIP
    >>> search.run(evaluations=40).best  # doctest: +SKIP
"""

from __future__ import annotations

from typing import Any

import numpy as np

from modelly.calibrate.gp import GaussianProcess, expected_improvement
from modelly.calibrate.optimize import OBJECTIVE, PointEstimate
from modelly.calibrate.posterior import Posterior
from modelly.calibrate.simulator import DEFAULT_EXECUTOR, Execution, Stream, generator

DEFAULT_EVALUATIONS = 30
DEFAULT_INITIAL = 10
CANDIDATES = 2000


class BayesOpt(PointEstimate):
    """Gaussian-process Bayesian optimisation of the total distance (see the module docstring)."""

    method = "bayes-opt"
    key = 4

    def _evaluate(self, units: np.ndarray, execution: Execution) -> None:
        """Run the points ``units`` and record their total distances."""
        distances, summaries = self.measure(self.simulate(units, execution))
        for i, unit in enumerate(units):
            self.record(unit, distances[i], {n: s[i] for n, s in summaries.items()})

    def _initial(self, count: int) -> np.ndarray:
        """``count`` Latin-hypercube points of the unit box, from the design stream."""
        from scipy.stats import qmc  # noqa: PLC0415 - lazy import

        rng = generator(self.seed, Stream.DESIGN, self.key)
        design: np.ndarray = qmc.LatinHypercube(len(self.names), rng=rng).random(count)
        return design

    def _next(self, iteration: int) -> np.ndarray:
        """The candidate of largest expected improvement under the fitted process."""
        x = np.vstack([entry["unit"] for entry in self.evaluations])
        y = np.array([entry["row"][OBJECTIVE] for entry in self.evaluations])
        process = GaussianProcess.fit(x, y)
        rng = generator(self.seed, Stream.PROPOSAL, self.key, iteration)
        candidates = rng.random((CANDIDATES, len(self.names)))
        mean, sd = process.predict(candidates)
        best: np.ndarray = candidates[
            int(np.argmax(expected_improvement(mean, sd, float(y.min()))))
        ]
        return best

    def run(
        self,
        evaluations: int = DEFAULT_EVALUATIONS,
        initial: int = DEFAULT_INITIAL,
        executor: Any = DEFAULT_EXECUTOR,
        **options: Any,
    ) -> Posterior:
        """``initial`` design points (run together), then the rest one by one; the best point.

        ``max_parallel`` and executor options go in ``options``.
        """
        if not 1 <= initial <= evaluations:
            raise ValueError("need 1 <= initial <= evaluations")
        max_parallel = options.pop("max_parallel", None)
        self.evaluations = []
        with Execution(executor, max_parallel, options) as execution:
            self._evaluate(self._initial(initial), execution)
            for iteration in range(evaluations - initial):
                self._evaluate(self._next(iteration)[None, :], execution)
        return self.estimate()
