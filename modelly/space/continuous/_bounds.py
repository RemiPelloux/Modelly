"""Arithmetic helpers of ``ContinuousSpace``: cached bounds and torus distances."""

from __future__ import annotations

import numpy as np


def float_bounds(dimensions: np.ndarray) -> tuple[tuple[float, float], ...] | None:
    """Each dimension's ``(low, high)`` as Python floats, as numpy compares them.

    A float64 point is compared with numeric bounds in float64, so these floats
    give the same answers. ``None`` when ``dimensions`` is not a numeric
    ``(ndims, 2)`` array (``in_bounds`` then compares arrays).
    """
    if (
        dimensions.dtype.kind not in "biuf"
        or dimensions.ndim != 2
        or dimensions.shape[1] != 2
    ):
        return None
    return tuple((low, high) for low, high in dimensions.astype(np.float64).tolist())


def torus_distances(
    point: np.ndarray, positions: np.ndarray, size: np.ndarray
) -> np.ndarray:
    """Euclidean distances across the wrap, computed in place in one temporary."""
    delta = point - positions
    np.abs(delta, out=delta)
    np.minimum(delta, np.subtract(size, delta), out=delta)
    np.multiply(delta, delta, out=delta)
    # + is much faster than np.sum or array.sum, and keeps the summation order
    dists = delta[:, 0].copy()
    for i in range(1, positions.shape[1]):
        dists += delta[:, i]
    return np.sqrt(dists, out=dists)
