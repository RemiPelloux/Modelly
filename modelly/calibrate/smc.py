"""ABC-SMC: approximate Bayesian computation by sequential Monte Carlo.

Generation 0 samples the priors. Each later generation sets its tolerance to a
quantile of the previous generation's distances, proposes particles by drawing
an ancestor by weight and moving it with the perturbation kernel
(:mod:`modelly.calibrate.kernels`), keeps those whose distance is within the
tolerance, and weights them by prior over proposal density (Toni et al., 2009;
Beaumont et al., 2009).

Proposals are made in batches of ``particles``; a generation keeps the first
``particles`` accepted in proposal order. Batch ``b`` of generation ``g`` draws
from the stream ``(PROPOSAL, g, b)`` and runs with the seeds of ``(g, b)``, so
the posterior is the same on every executor and after a resume.

Example:
    >>> calibration = ABCSMC(
    ...     model=Epidemic,
    ...     priors={"beta": Prior.uniform(0.05, 0.5), "gamma": Prior.log_normal(-2, 0.5)},
    ...     targets=[Target("infected", observed=cases)],
    ...     steps=60,
    ...     seed=2027,
    ... )  # doctest: +SKIP
    >>> posterior = calibration.run(budget=5000, executor="processes")  # doctest: +SKIP
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from modelly.calibrate.base import Calibration, CalibrationError
from modelly.calibrate.kernels import Kernel
from modelly.calibrate.posterior import Posterior
from modelly.calibrate.simulator import (
    DEFAULT_EXECUTOR,
    Batch,
    Execution,
    Stream,
    generator,
)

DEFAULT_PARTICLES = 100
DEFAULT_QUANTILE = 0.5
DEFAULT_GENERATIONS = 5
DEFAULT_MIN_ACCEPTANCE = 0.01
SMC_KEY = 1  # first element of every batch key of this method
GENERATIONS, BUDGET = "generations", "budget"
TOLERANCE, ACCEPTANCE = "min_tolerance", "min_acceptance"


@dataclass
class Accepted:
    """The particles of one proposal batch that met the tolerance."""

    samples: dict[str, list[Any]]
    distances: np.ndarray
    summaries: dict[str, np.ndarray]


@dataclass
class Generation:
    """One accepted population: samples, weights, distances, summaries and costs."""

    samples: dict[str, list[Any]]
    weights: np.ndarray
    distances: np.ndarray
    summaries: dict[str, np.ndarray]
    tolerance: float
    runs: int
    acceptance: float

    @property
    def effective_sample_size(self) -> float:
        """Kish's effective sample size of the normalised weights."""
        return float(1.0 / np.sum(self.weights**2))


class ABCSMC(Calibration):
    """ABC-SMC with an adaptive tolerance schedule.

    Takes the :class:`~modelly.calibrate.base.Calibration` arguments and:

    Args:
        particles: the population size (and the size of a proposal batch).
        quantile: the next tolerance is this quantile of the last distances.
        min_tolerance: stop once the tolerance reaches this value.
        min_acceptance: stop when a generation accepts a smaller share of its
            proposals; also bounds the cost of one generation.
    """

    method = "abc-smc"

    def __init__(
        self,
        *args: Any,
        particles: int = DEFAULT_PARTICLES,
        quantile: float = DEFAULT_QUANTILE,
        min_tolerance: float = 0.0,
        min_acceptance: float = DEFAULT_MIN_ACCEPTANCE,
        **kwargs: Any,
    ) -> None:
        """Check the settings; nothing runs before ``run``."""
        super().__init__(*args, **kwargs)
        if particles < 1 or not 0 < quantile <= 1 or not 0 < min_acceptance <= 1:
            raise ValueError(
                "particles >= 1, 0 < quantile <= 1, 0 < min_acceptance <= 1"
            )
        self.particles, self.quantile = particles, quantile
        self.min_tolerance, self.min_acceptance = min_tolerance, min_acceptance
        self.history: list[Generation] = []
        self.stopped: str | None = None

    @property
    def runs(self) -> int:
        """Model runs made by the accepted generations."""
        return sum(generation.runs for generation in self.history)

    def run(
        self,
        budget: int | None = None,
        generations: int = DEFAULT_GENERATIONS,
        executor: Any = DEFAULT_EXECUTOR,
        max_parallel: int | None = None,
        **options: Any,
    ) -> Posterior:
        """Add generations until one of the stopping rules holds; the last posterior.

        Stops after ``generations`` generations in all, before a generation
        that would take the model runs past ``budget``, when the tolerance
        reaches ``min_tolerance`` or the acceptance rate falls below
        ``min_acceptance``. ``checkpoint=path`` (in ``options``) saves after
        every generation. Calling ``run`` again, after ``load`` or with a
        larger ``generations``, goes on from the last generation.
        """
        checkpoint = options.pop("checkpoint", None)
        self.stopped = None
        with Execution(executor, max_parallel, options) as execution:
            while self.stopped is None:
                self.stopped = self._stop_before(generations)
                if self.stopped is None:
                    self._advance(budget, execution)
                if checkpoint is not None:
                    self.save(checkpoint)
        if not self.history:
            raise CalibrationError(
                f"no generation completed (stopped by {self.stopped})"
            )
        return self.posterior_of(self.history[-1])

    def _stop_before(self, generations: int) -> str | None:
        """The rule that stops the run before the next generation, if any."""
        if len(self.history) >= generations:
            return GENERATIONS
        if self.history and self.history[-1].tolerance <= self.min_tolerance:
            return TOLERANCE
        if self.history and self.history[-1].acceptance < self.min_acceptance:
            return ACCEPTANCE
        return None

    def _advance(self, budget: int | None, execution: Execution) -> None:
        """Run the next generation and keep it, or set ``stopped`` to why it failed."""
        index, tolerance = len(self.history), self._tolerance()
        kernel = self._kernel()
        parts: list[Accepted] = []
        proposals = kept = 0
        while kept < self.particles:
            self.stopped = self._stop_within(budget, proposals, kept)
            if self.stopped is not None:
                return
            batch = (index, proposals // self.particles)
            parts.append(self._batch(batch, kernel, tolerance, execution))
            proposals += self.particles
            kept += len(parts[-1].distances)
        self.history.append(self._generation(parts, kernel, tolerance, proposals))

    def _stop_within(self, budget: int | None, proposals: int, kept: int) -> str | None:
        """The rule that abandons the current generation before its next batch, if any."""
        cost = (proposals + self.particles) * self.replicates
        if budget is not None and self.runs + cost > budget:
            return BUDGET
        hopeless = proposals * self.min_acceptance >= self.particles
        if proposals and hopeless and kept / proposals < self.min_acceptance:
            return ACCEPTANCE
        return None

    def _tolerance(self) -> float:
        """Infinite for generation 0, else the quantile of the last distances (>= the minimum)."""
        if not self.history:
            return math.inf
        value = float(np.quantile(self.history[-1].distances, self.quantile))
        return max(value, self.min_tolerance)

    def _kernel(self) -> Kernel | None:
        """The kernel moving the last population (none before generation 0)."""
        if not self.history:
            return None
        last = self.history[-1]
        return Kernel.fit(self.priors, last.samples, last.weights)

    def _batch(
        self,
        batch: tuple[int, int],
        kernel: Kernel | None,
        tolerance: float,
        execution: Execution,
    ) -> Accepted:
        """Propose and run one batch; the particles within ``tolerance``."""
        rng = generator(self.seed, Stream.PROPOSAL, SMC_KEY, *batch)
        if kernel is None:
            samples = {
                n: list(p.sample(rng, self.particles)) for n, p in self.priors.items()
            }
        else:
            samples = kernel.propose(rng, self.particles)
        points = self.points(samples)
        distances, summaries = self.evaluate(
            Batch((SMC_KEY, *batch), points), execution
        )
        keep = np.flatnonzero(distances <= tolerance)
        chosen = {n: [values[i] for i in keep] for n, values in samples.items()}
        return Accepted(
            chosen, distances[keep], {n: s[keep] for n, s in summaries.items()}
        )

    def _generation(
        self,
        parts: list[Accepted],
        kernel: Kernel | None,
        tolerance: float,
        proposals: int,
    ) -> Generation:
        """The first ``particles`` accepted, in proposal order, with importance weights."""
        size = self.particles
        samples = {
            n: [v for part in parts for v in part.samples[n]][:size] for n in self.names
        }
        distances = np.concatenate([part.distances for part in parts])[:size]
        summaries = {
            t.name: np.concatenate([part.summaries[t.name] for part in parts])[:size]
            for t in self.targets
        }
        weights = np.full(size, 1.0 / size)
        if kernel is not None:
            log = kernel.importance(samples)
            weights = np.exp(log - log.max())
            weights /= weights.sum()
        runs, acceptance = proposals * self.replicates, size / proposals
        return Generation(
            samples, weights, distances, summaries, tolerance, runs, acceptance
        )

    def posterior_of(self, generation: Generation) -> Posterior:
        """The Posterior of ``generation``, with the run's diagnostics in ``info``."""
        g = generation
        posterior = self.posterior(g.samples, g.weights, g.distances, g.summaries)
        posterior.info = {"generations": len(self.history), "tolerance": g.tolerance}
        posterior.info |= {"runs": self.runs, "acceptance": g.acceptance}
        posterior.info |= {"stopped": self.stopped}
        return posterior

    def trace(self) -> pd.DataFrame:
        """One row per generation: tolerance, acceptance rate, effective sample size, runs."""
        return pd.DataFrame(
            [
                {
                    "generation": index,
                    "tolerance": g.tolerance,
                    "acceptance": g.acceptance,
                    "ess": g.effective_sample_size,
                    "runs": g.runs,
                }
                for index, g in enumerate(self.history)
            ]
        )
