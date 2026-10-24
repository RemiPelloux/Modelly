"""Distances between a simulated summary and the observed one.

A distance is any function ``distance(simulated, observed) -> float`` of two
arrays of the same shape; smaller is closer. Example:

    >>> import numpy as np
    >>> rmse(np.array([1.0, 2.0]), np.array([1.0, 4.0]))
    1.4142135623730951
    >>> weighted([1.0, 0.0])(np.array([1.0, 2.0]), np.array([1.0, 4.0]))
    0.0

Every built-in is a module-level function or a picklable object, so a
calibration that uses them can be saved and resumed.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

Distance = Callable[[np.ndarray, np.ndarray], float]


def _pair(simulated: np.ndarray, observed: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Both arrays as float, flattened, with a ValueError when their sizes differ."""
    sim = np.asarray(simulated, dtype=float).ravel()
    obs = np.asarray(observed, dtype=float).ravel()
    if sim.shape != obs.shape:
        raise ValueError(f"simulated has {sim.size} values, observed {obs.size}")
    return sim, obs


def rmse(simulated: np.ndarray, observed: np.ndarray) -> float:
    """Root mean squared error."""
    sim, obs = _pair(simulated, observed)
    return float(np.sqrt(np.mean((sim - obs) ** 2)))


def mae(simulated: np.ndarray, observed: np.ndarray) -> float:
    """Mean absolute error."""
    sim, obs = _pair(simulated, observed)
    return float(np.mean(np.abs(sim - obs)))


def euclidean(simulated: np.ndarray, observed: np.ndarray) -> float:
    """The Euclidean norm of the difference (for vectors of summary statistics)."""
    sim, obs = _pair(simulated, observed)
    return float(np.linalg.norm(sim - obs))


def wasserstein(simulated: np.ndarray, observed: np.ndarray) -> float:
    """The Wasserstein-1 distance between the two sets of values as distributions.

    The values are compared as samples, whatever their order or count.
    """
    from scipy.stats import wasserstein_distance  # noqa: PLC0415 - lazy import

    sim = np.asarray(simulated, dtype=float).ravel()
    obs = np.asarray(observed, dtype=float).ravel()
    return float(wasserstein_distance(sim, obs))


@dataclass(frozen=True)
class Weighted:
    """Root of the weighted mean of squared errors; one weight per value."""

    weights: tuple[float, ...]

    def __call__(self, simulated: np.ndarray, observed: np.ndarray) -> float:
        """The weighted RMSE of ``simulated`` against ``observed``."""
        sim, obs = _pair(simulated, observed)
        weights = np.asarray(self.weights, dtype=float)
        if weights.shape != sim.shape:
            raise ValueError(f"{weights.size} weights for {sim.size} values")
        return float(np.sqrt(np.sum(weights * (sim - obs) ** 2) / np.sum(weights)))


def weighted(weights: Sequence[float]) -> Weighted:
    """A weighted RMSE: ``weights[i]`` scales the squared error of value ``i``."""
    values = tuple(float(w) for w in weights)
    if not values or min(values) < 0 or sum(values) == 0:
        raise ValueError("weights must be >= 0 and not all zero")
    return Weighted(values)


DISTANCES: dict[str, Distance] = {
    "rmse": rmse,
    "mae": mae,
    "euclidean": euclidean,
    "wasserstein": wasserstein,
}
