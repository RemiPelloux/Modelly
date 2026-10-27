"""Sampling helpers for building experiment designs."""

from __future__ import annotations

import numpy as np


def rescale_samples(
    samples: np.ndarray,
    ranges: np.ndarray,
    *,
    inplace: bool = False,
) -> np.ndarray:
    """Rescale samples from the unit interval [0, 1] to parameter ranges.

    Args:
        samples: Array of shape (n, d) drawn from the unit interval.
        ranges: Array of shape (d, 2) giving ``[[min, max], ...]`` per parameter.
        inplace: If True, ``samples`` is overwritten with the result; if False
            (default), a new array is returned.

    Returns:
        The rescaled samples, shape (n, d).
    """
    samples = np.asarray(samples)
    ranges = np.asarray(ranges)

    mins = ranges[:, 0]
    scale = ranges[:, 1] - mins

    if inplace:
        samples *= scale
        samples += mins
        return samples

    rescaled: np.ndarray = samples * scale + mins
    return rescaled
