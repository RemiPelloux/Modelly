"""A small Gaussian-process regressor on numpy and scipy (basic, by design).

Used by :class:`~modelly.calibrate.bayesopt.BayesOpt` and the sensitivity
emulator. Inputs are points of the unit cube; the kernel is a squared
exponential with one length scale per input plus a noise term, fitted by
maximising the log marginal likelihood with L-BFGS-B from a fixed start. It is
meant for a few hundred points in a handful of dimensions; for more, use a
dedicated library.

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
    def fit(cls, x: np.ndarray, y: np.ndarray) -> GaussianProcess:
        """Fit to inputs ``x[point, dimension]`` in the unit cube and outputs ``y[point]``."""
        from scipy.linalg import cho_factor, cho_solve  # noqa: PLC0415 - lazy import
        from scipy.optimize import minimize  # noqa: PLC0415 - lazy import

        x, y = np.asarray(x, float), np.asarray(y, float)
        mean, scale = float(y.mean()), float(y.std()) or 1.0
        standard = (y - mean) / scale
        dims = x.shape[1]
        start = np.append(np.full(dims, np.log(START_LENGTH)), np.log(START_NOISE))
        bounds = [LOG_LENGTH_BOUNDS] * dims + [LOG_NOISE_BOUNDS]
        found = minimize(
            _negative_log_likelihood, start, (x, standard), "L-BFGS-B", bounds=bounds
        )
        lengths, noise = np.exp(found.x[:-1]), float(np.exp(found.x[-1]))
        covariance = _kernel(x, x, lengths) + (noise + JITTER) * np.eye(len(x))
        factor = cho_factor(covariance, lower=True)
        alpha = cho_solve(factor, standard)
        return cls(x, lengths, noise, alpha, factor[0], mean, scale)

    def predict(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """The predictive mean and standard deviation at the rows of ``x``."""
        from scipy.linalg import solve_triangular  # noqa: PLC0415 - lazy import

        cross = _kernel(np.asarray(x, float), self.x, self.lengths)
        mean = cross @ self.alpha
        solved = solve_triangular(self.factor, cross.T, lower=True)
        variance = np.clip(1.0 - np.sum(solved**2, axis=0), 0.0, None)
        return self.mean + self.scale * mean, self.scale * np.sqrt(variance)


def expected_improvement(mean: np.ndarray, sd: np.ndarray, best: float) -> np.ndarray:
    """Expected improvement below ``best`` (minimisation) of normal predictions."""
    from scipy.stats import norm  # noqa: PLC0415 - lazy import

    sd = np.maximum(sd, JITTER)
    z = (best - mean) / sd
    return (best - mean) * norm.cdf(z) + sd * norm.pdf(z)
