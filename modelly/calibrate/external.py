"""Bayesian optimisation by an outside library, behind a two-call adapter.

:class:`ExternalBayesOpt` searches the same unit box over the priors as
:class:`~modelly.calibrate.bayesopt.BayesOpt`, with the same common random
numbers, but asks an outside optimiser where to run next. An optimiser is any
object with ``ask() -> unit point`` and ``tell(unit, value)``; ``backend`` names
a built-in adapter or is a factory ``(dimensions, seed) -> optimiser``.

The built-in adapter is ``"optuna"``: an optuna study in memory, minimising the
total distance, with optuna's TPE sampler (a sequential model-based optimiser)
seeded from the calibration's seed, or any optuna sampler given as ``sampler=``.
optuna is imported only when the search starts: ``pip install
"modelly-abm[calibrate]"``. Like ``BayesOpt``, it returns the best point found,
not a posterior.

Example:
    >>> search = ExternalBayesOpt(Epidemic, priors, targets, steps=60, seed=3)  # doctest: +SKIP
    >>> search.run(evaluations=40).best  # doctest: +SKIP
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Protocol

import numpy as np

from modelly._optional import require
from modelly.calibrate.optimize import PointEstimate
from modelly.calibrate.posterior import Posterior
from modelly.calibrate.simulator import DEFAULT_EXECUTOR, Execution

DEFAULT_EVALUATIONS = 30
EXTRA = "calibrate"
UNIT_LOW, UNIT_HIGH = 0.0, 1.0


class Optimiser(Protocol):
    """What an outside optimiser provides: a point to run, then its value."""

    def ask(self) -> Sequence[float]:
        """The next point to evaluate, in the unit cube."""

    def tell(self, unit: Sequence[float], value: float) -> None:
        """The objective at the point ``ask`` returned last (lower is better)."""


class OptunaBackend:
    """optuna's ask-and-tell interface over the unit cube, minimising.

    Args:
        dimensions: the number of fitted parameters.
        seed: the seed of the default TPE sampler.
        sampler: an optuna sampler to use instead.
    """

    def __init__(self, dimensions: int, seed: int, sampler: Any = None) -> None:
        """Create the in-memory study."""
        optuna = require("optuna", EXTRA)
        uniform = optuna.distributions.FloatDistribution(UNIT_LOW, UNIT_HIGH)
        self.names = [f"u{i}" for i in range(dimensions)]
        self.space = dict.fromkeys(self.names, uniform)
        chosen = sampler or optuna.samplers.TPESampler(seed=seed)
        self.study = optuna.create_study(direction="minimize", sampler=chosen)
        self.trial: Any = None

    def ask(self) -> list[float]:
        """The study's next trial, as a unit point."""
        self.trial = self.study.ask(self.space)
        return [self.trial.params[name] for name in self.names]

    def tell(self, unit: Sequence[float], value: float) -> None:
        """Close the open trial with ``value``."""
        self.study.tell(self.trial, value)


BACKENDS: dict[str, Callable[..., Optimiser]] = {"optuna": OptunaBackend}


class ExternalBayesOpt(PointEstimate):
    """Bayesian optimisation of the total distance by an outside optimiser.

    Args:
        *args: as for :class:`~modelly.calibrate.base.Calibration`.
        backend: ``"optuna"``, or a factory ``(dimensions, seed, **options) -> Optimiser``.
        backend_options: keyword arguments of the backend (``sampler=`` for optuna).
        **kwargs: as for :class:`~modelly.calibrate.base.Calibration`.
    """

    method = "external-bayes-opt"
    key = 5

    def __init__(
        self,
        *args: Any,
        backend: str | Callable[..., Optimiser] = "optuna",
        backend_options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Check the priors and the backend; nothing runs before ``run``."""
        super().__init__(*args, **kwargs)
        if isinstance(backend, str) and backend not in BACKENDS:
            raise ValueError(f"backend must be one of {sorted(BACKENDS)} or a factory")
        self.backend = backend
        self.backend_options = dict(backend_options or {})

    def optimiser(self) -> Optimiser:
        """A fresh optimiser over the box, seeded with the calibration's seed."""
        factory = BACKENDS.get(self.backend, self.backend)  # type: ignore[arg-type]
        return factory(len(self.names), self.seed, **self.backend_options)

    def run(
        self,
        evaluations: int = DEFAULT_EVALUATIONS,
        executor: Any = DEFAULT_EXECUTOR,
        **options: Any,
    ) -> Posterior:
        """``evaluations`` points, one at a time, where the optimiser asks; the best point.

        ``max_parallel`` and executor options go in ``options``. A rerun into the same
        store asks the same points (same seed) and reads their runs from the store.
        """
        if evaluations < 1:
            raise ValueError("need at least one evaluation")
        max_parallel = options.pop("max_parallel", None)
        optimiser = self.optimiser()
        self.evaluations = []
        with Execution(executor, max_parallel, options) as execution:
            for _ in range(evaluations):
                unit = np.clip(np.asarray(optimiser.ask(), float), UNIT_LOW, UNIT_HIGH)
                distances, summaries = self.measure(self.simulate([unit], execution))
                summary = {name: values[0] for name, values in summaries.items()}
                optimiser.tell(unit, self.record(unit, distances[0], summary))
        return self.estimate()
