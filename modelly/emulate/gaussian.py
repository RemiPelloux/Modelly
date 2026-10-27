"""A Gaussian-process emulator: one process per output, on the unit cube.

Each output gets the Gaussian process of :mod:`modelly.calibrate.gp` (squared
exponential kernel, one length scale per input, a fitted noise term), fitted
with restarts by default. Besides the mean and standard deviation it gives the
predictive covariance and the variance after more runs (``condition``), which
the active-learning designs of :mod:`modelly.emulate.active` use.

Example:
    >>> import numpy as np
    >>> units = np.linspace(0, 1, 9)[:, None]
    >>> emulator = GaussianEmulator.fit(units, np.sin(6 * units[:, 0]))
    >>> mean, sd = emulator.predict([[0.5]])
    >>> bool(abs(mean[0, 0] - np.sin(3.0)) < 0.05)
    True
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from modelly.calibrate.gp import GaussianProcess
from modelly.emulate.base import Emulator, as_columns, output_names
from modelly.experiments.space import ScenarioSpace

CHUNK = 4096  # rows predicted at once: bounds the memory of the kernel matrices


@dataclass(eq=False)
class GaussianEmulator(Emulator):
    """Independent Gaussian processes, one per output.

    Attributes:
        processes: the fitted processes, one per output.
        names: the outputs.
        space: the space whose unit cube the inputs are, if known.
    """

    processes: list[GaussianProcess]
    names: list[str]
    space: ScenarioSpace | None = None

    @classmethod
    def fit(
        cls,
        units: np.ndarray,
        values: np.ndarray,
        names: Sequence[str] | None = None,
        *,
        space: ScenarioSpace | None = None,
        restarts: bool = True,
    ) -> GaussianEmulator:
        """Fit one process per column of ``values``; ``restarts`` as in ``GaussianProcess.fit``."""
        units = np.atleast_2d(np.asarray(units, float))
        values = as_columns(values)
        processes = [
            GaussianProcess.fit(units, column, restarts=restarts) for column in values.T
        ]
        return cls(processes, output_names(values.shape[1], names), space)

    def predict(self, units: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """The mean and standard deviation of the fitted functions, ``[point, output]``."""
        units = np.atleast_2d(np.asarray(units, float))
        means, sds = [], []
        for start in range(0, max(len(units), 1), CHUNK):
            pairs = [p.predict(units[start : start + CHUNK]) for p in self.processes]
            means.append(np.column_stack([mean for mean, _ in pairs]))
            sds.append(np.column_stack([sd for _, sd in pairs]))
        return np.vstack(means), np.vstack(sds)

    def covariance(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """The predictive covariance ``[output, row of a, row of b]``."""
        return np.stack([process.covariance(a, b) for process in self.processes])

    @property
    def noise_variance(self) -> np.ndarray:
        """The fitted noise variance of every output (run-to-run scatter)."""
        return np.array([process.noise_variance for process in self.processes])

    def condition(self, units: np.ndarray) -> GaussianEmulator:
        """The emulator as if ``units`` had been run and returned the predicted mean.

        The hyperparameters are kept, so the standard deviations are those the
        emulator would have after the runs: how a batch is chosen.
        """
        processes = [process.condition(units) for process in self.processes]
        return GaussianEmulator(processes, self.names, self.space)

    def _subset(self, index: int) -> GaussianEmulator:
        """The emulator of the output in column ``index``."""
        return GaussianEmulator(
            [self.processes[index]], [self.names[index]], self.space
        )
