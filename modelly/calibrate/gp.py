"""A small Gaussian-process regressor on numpy and scipy (basic, by design).

Used by :class:`~modelly.calibrate.bayesopt.BayesOpt`, the sensitivity emulator
and :mod:`modelly.emulate`. Inputs are points of the unit cube; the kernel is a
squared exponential with one length scale per input plus a noise term, fitted
by maximising the log marginal likelihood with L-BFGS-B from a fixed start
(``restarts=True`` adds a few more starts and keeps the best). It is meant for
a few hundred points in a handful of dimensions; for more, use a dedicated
library.

Example:
    >>> import numpy as np
    >>> x = np.linspace(0, 1, 8)[:, None]
    >>> gp = GaussianProcess.fit(x, np.sin(6 * x[:, 0]))
    >>> mean, sd = gp.predict(np.array([[0.5]]))
    >>> bool(abs(mean[0] - np.sin(3.0)) < 0.05)
    True
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

START_LENGTH = 0.3
START_NOISE = 1e-3
LOG_LENGTH_BOUNDS = (np.log(1e-2), np.log(1e1))
LOG_NOISE_BOUNDS = (np.log(1e-8), np.log(1.0))
JITTER = 1e-10
LOG_TWO_PI = np.log(2 * np.pi)
# Extra (length scale, noise) starts of a fit with restarts: short, long and noisy fits.
RESTARTS = ((0.1, 1e-6), (0.3, 1e-6), (1.0, 1e-6), (3.0, 1e-4))


def _kernel(a: np.ndarray, b: np.ndarray, lengths: np.ndarray) -> np.ndarray:
    """The squared-exponential covariance between the rows of ``a`` and ``b``."""
    diff = (a[:, None, :] - b[None, :, :]) / lengths
    return np.exp(-0.5 * np.sum(diff**2, axis=2))


def _negative_log_likelihood(theta: np.ndarray, x: np.ndarray, y: np.ndarray) -> float:
    """Minus the log marginal likelihood of standardised ``y`` at log parameters ``theta``."""
    from scipy.linalg import cho_factor, cho_solve  # noqa: PLC0415 - lazy import

    lengths, noise = np.exp(theta[:-1]), np.exp(theta[-1])
    covariance = _kernel(x, x, lengths) + (noise + JITTER) * np.eye(len(x))
    try:
        factor = cho_factor(covariance, lower=True)
    except np.linalg.LinAlgError:
        return float(np.inf)
    alpha = cho_solve(factor, y)
    log_det = 2 * np.sum(np.log(np.diag(factor[0])))
    return float(0.5 * y @ alpha + 0.5 * log_det + 0.5 * len(x) * LOG_TWO_PI)


def _hyperparameters(
    x: np.ndarray, standard: np.ndarray, restarts: bool
) -> tuple[np.ndarray, float]:
    """The fitted length scales and noise: one start, or the best of several."""
    from scipy.optimize import minimize  # noqa: PLC0415 - lazy import

    dims = x.shape[1]
    bounds = [LOG_LENGTH_BOUNDS] * dims + [LOG_NOISE_BOUNDS]
    starts = [(START_LENGTH, START_NOISE), *(RESTARTS if restarts else ())]
    # A finite-difference gradient: an analytic one needs the inverse covariance, a
    # matrix product that a multi-threaded BLAS makes far slower on a busy machine.
    found = [
        minimize(
            _negative_log_likelihood,
            np.append(np.full(dims, np.log(length)), np.log(noise)),
            (x, standard),
            "L-BFGS-B",
            bounds=bounds,
        )
        for length, noise in starts
    ]
    best = min(found, key=lambda result: result.fun)
    return np.exp(best.x[:-1]), float(np.exp(best.x[-1]))


@dataclass
class GaussianProcess:
    """A fitted Gaussian process: training data, hyperparameters, and the solved system."""

    x: np.ndarray
    lengths: np.ndarray
    noise: float
    alpha: np.ndarray
    factor: np.ndarray
    mean: float
    scale: float

    @classmethod
    def fit(
        cls, x: np.ndarray, y: np.ndarray, *, restarts: bool = False
    ) -> GaussianProcess:
        """Fit to inputs ``x[point, dimension]`` in the unit cube and outputs ``y[point]``.

        ``restarts`` also starts the likelihood search from :data:`RESTARTS`
        and keeps the most likely fit: slower, and much less often stuck at a
        fit that calls everything noise.
        """
        x, y = np.asarray(x, float), np.asarray(y, float)
        mean, scale = float(y.mean()), float(y.std()) or 1.0
        standard = (y - mean) / scale
        lengths, noise = _hyperparameters(x, standard, restarts)
        return cls.solve(x, standard, (lengths, noise), (mean, scale))

    @classmethod
    def solve(
        cls,
        x: np.ndarray,
        standard: np.ndarray,
        hyperparameters: tuple[np.ndarray, float],
        standardisation: tuple[float, float],
    ) -> GaussianProcess:
        """The process with given ``(lengths, noise)`` through standardised outputs ``standard``."""
        from scipy.linalg import cho_factor, cho_solve  # noqa: PLC0415 - lazy import

        lengths, noise = hyperparameters
        covariance = _kernel(x, x, lengths) + (noise + JITTER) * np.eye(len(x))
        factor = cho_factor(covariance, lower=True)
        alpha = cho_solve(factor, standard)
        return cls(x, lengths, noise, alpha, factor[0], *standardisation)

    def predict(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """The predictive mean and standard deviation at the rows of ``x``."""
        from scipy.linalg import solve_triangular  # noqa: PLC0415 - lazy import

        cross = _kernel(np.asarray(x, float), self.x, self.lengths)
        mean = cross @ self.alpha
        solved = solve_triangular(self.factor, cross.T, lower=True)
        variance = np.clip(1.0 - np.sum(solved**2, axis=0), 0.0, None)
        return self.mean + self.scale * mean, self.scale * np.sqrt(variance)

    def covariance(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """The predictive covariance ``[row of a, row of b]`` of the fitted function."""
        from scipy.linalg import solve_triangular  # noqa: PLC0415 - lazy import

        a, b = np.asarray(a, float), np.asarray(b, float)
        left = solve_triangular(
            self.factor, _kernel(a, self.x, self.lengths).T, lower=True
        )
        right = solve_triangular(
            self.factor, _kernel(b, self.x, self.lengths).T, lower=True
        )
        prior = _kernel(a, b, self.lengths)
        return self.scale**2 * (prior - left.T @ right)

    @property
    def noise_variance(self) -> float:
        """The fitted noise (nugget) variance, in the output's units."""
        return self.noise * self.scale**2

    def condition(self, x: np.ndarray, y: np.ndarray | None = None) -> GaussianProcess:
        """The process with the points ``x`` (outputs ``y``) added, hyperparameters kept.

        Without ``y`` the new points take the predicted mean (the "kriging
        believer"): the mean is unchanged and the variance is what it would be
        after running them, which is how a batch of runs is chosen.
        """
        x = np.atleast_2d(np.asarray(x, float))
        y = self.predict(x)[0] if y is None else np.asarray(y, float)
        lower = np.tril(self.factor)
        known = lower @ (lower.T @ self.alpha)
        standard = np.append(known, (y - self.mean) / self.scale)
        return self.solve(
            np.vstack([self.x, x]),
            standard,
            (self.lengths, self.noise),
            (self.mean, self.scale),
        )


def expected_improvement(mean: np.ndarray, sd: np.ndarray, best: float) -> np.ndarray:
    """Expected improvement below ``best`` (minimisation) of normal predictions."""
    from scipy.stats import norm  # noqa: PLC0415 - lazy import

    sd = np.maximum(sd, JITTER)
    z = (best - mean) / sd
    return (best - mean) * norm.cdf(z) + sd * norm.pdf(z)
