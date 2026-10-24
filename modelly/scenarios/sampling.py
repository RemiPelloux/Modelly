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

    Parameters
    ----------
    samples : ndarray (n, d)
        Samples drawn from the unit interval.
    ranges : ndarray (d, 2)
        Parameter ranges given as [[min, max], ...].
    inplace : bool, optional
        If True, the input ``samples`` array is modified in place.
        If False (default), a new array containing the rescaled samples
        is returned.

    Returns:
    -------
    ndarray (n, d)
        Rescaled samples.

    Notes:
    -----
    The rescaling is performed using NumPy broadcasting. If ``inplace=True``,
    the original ``samples`` array is overwritten.
    """
    samples = np.asarray(samples)
    ranges = np.asarray(ranges)

    mins = ranges[:, 0]
    scale = ranges[:, 1] - mins

    if inplace:
        samples *= scale
        samples += mins
        return samples

    return samples * scale + mins
