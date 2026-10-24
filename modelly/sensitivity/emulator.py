"""A Gaussian-process emulator: analyse an expensive model from a few hundred runs.

``emulate`` runs the model at a Latin hypercube of ``samples`` points and fits
the basic Gaussian process of :mod:`modelly.calibrate.gp` to the output. The
returned :class:`Emulator` stands in for the model in ``oat``, ``morris``,
``sobol`` and ``pawn``, which then cost no further runs::

    surrogate = emulate(Epidemic, space, "peak", samples=200, steps=120)
    print(surrogate.r2)            # leave-one-out accuracy, near 1 is good
    sobol(surrogate, space, samples=4096)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from modelly.calibrate.gp import GaussianProcess
from modelly.calibrate.simulator import Stream
from modelly.experiments.space import ScenarioSpace
from modelly.sensitivity.study import Study

DEFAULT_SAMPLES = 200
EMULATOR_KEY = 15
HOLDOUT_SHARE = 0.2


@dataclass
class Emulator:
    """A fitted Gaussian process over the unit cube of ``space``.

    Attributes:
        space: the parameter space it was fitted over.
        process: the fitted Gaussian process.
        units: the training points.
        values: the model's outputs at them.
        r2: the share of variance explained on held-out training points.
    """

    space: ScenarioSpace
    process: GaussianProcess
    units: np.ndarray
    values: np.ndarray
    r2: float

    def predict_unit(self, units: np.ndarray) -> np.ndarray:
        """The predicted output at points of the unit cube."""
        return self.process.predict(np.atleast_2d(units))[0]


def _holdout_r2(
    units: np.ndarray, values: np.ndarray, rng: np.random.Generator
) -> float:
    """R squared of a process fitted without a random ``HOLDOUT_SHARE`` of the points."""
    order = rng.permutation(len(values))
    cut = max(1, int(HOLDOUT_SHARE * len(values)))
    test, train = order[:cut], order[cut:]
    process = GaussianProcess.fit(units[train], values[train])
    predicted = process.predict(units[test])[0]
    spread = np.sum((values[test] - values[test].mean()) ** 2)
    return (
        float(1 - np.sum((values[test] - predicted) ** 2) / spread) if spread else 1.0
    )


def emulate(
    model: Any,
    space: ScenarioSpace,
    output: Any = None,
    *,
    samples: int = DEFAULT_SAMPLES,
    **settings: Any,
) -> Emulator:
    """Run ``model`` at ``samples`` Latin-hypercube points and fit an Emulator.

    ``settings`` are the :class:`~modelly.sensitivity.study.Study` fields.
    """
    from scipy.stats import qmc  # noqa: PLC0415 - lazy import

    study = Study(model, space, output, **settings)
    rng = study.rng(Stream.DESIGN, EMULATOR_KEY)
    units = qmc.LatinHypercube(len(study.names), rng=rng).random(samples)
    values = study.evaluate(units, EMULATOR_KEY)
    r2 = _holdout_r2(units, values, study.rng(Stream.BOOTSTRAP, EMULATOR_KEY))
    return Emulator(space, GaussianProcess.fit(units, values), units, values, r2)
