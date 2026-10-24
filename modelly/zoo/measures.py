"""Summary statistics shared by the zoo models and their validation tests."""

from __future__ import annotations

import numpy as np


def gini(values: np.ndarray) -> float:
    """The Gini coefficient of non-negative ``values``: 0 equality, near 1 one holds all.

    Computed from the sorted values, ``G = sum_i (2 i - n - 1) x_(i) / (n sum x)``.

    Example:
        >>> gini(np.array([1, 1, 1, 1]))
        0.0
        >>> gini(np.array([0, 0, 0, 4]))
        0.75
    """
    x = np.sort(np.asarray(values, dtype=float))
    n = x.shape[0]
    total = x.sum()
    if n == 0 or total == 0:
        return 0.0
    ranks = np.arange(1, n + 1)
    return float(((2 * ranks - n - 1) * x).sum() / (n * total))


def clusters(values: np.ndarray, gap: float, min_share: float = 0.0) -> int:
    """The number of groups of 1-D ``values`` separated by more than ``gap``.

    Groups with fewer than ``min_share`` of the values (isolated extremists) are not
    counted.

    Example:
        >>> clusters(np.array([0.1, 0.11, 0.5, 0.52, 0.9]), gap=0.05)
        3
        >>> clusters(np.array([0.1, 0.11, 0.5, 0.52, 0.9]), gap=0.05, min_share=0.3)
        2
    """
    x = np.sort(np.asarray(values, dtype=float))
    if x.shape[0] == 0:
        return 0
    breaks = np.flatnonzero(np.diff(x) > gap)
    sizes = np.diff(np.concatenate(([0], breaks + 1, [x.shape[0]])))
    return int((sizes >= min_share * x.shape[0]).sum())
