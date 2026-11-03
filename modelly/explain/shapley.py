"""Shapley values of an emulator's prediction: how much each parameter moved it.

``shapley(predict, point, background)`` splits ``predict(point) - mean(predict(background))``
between the parameters exactly: the Shapley value of parameter ``j`` averages, over every
subset ``S`` of the other parameters, how much setting ``j`` to its value in ``point`` changes
the prediction when ``S`` is set too and the rest take their values from the background
sample (the *interventional* value function). The values add up to the difference, as Shapley
values must. Exact enumeration costs ``2**d`` background predictions for ``d`` parameters,
fine for the ten or so parameters an emulator usually has; an emulator makes each one cheap.

``predict`` is any function of unit-cube points ``[point, dimension]`` returning one value per
point, such as ``Emulator.select(name).predict_unit`` of ``modelly.emulate``.

Reference:
    Lundberg, S. M. and Lee, S.-I. (2017). A unified approach to interpreting model
    predictions. Advances in Neural Information Processing Systems 30, 4765-4774.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from itertools import combinations
from math import factorial

import numpy as np

MAX_DIMENSIONS = 16


def _value(predict, point: np.ndarray, background: np.ndarray, subset: tuple[int, ...]):
    """The mean prediction with the parameters ``subset`` set from ``point``."""
    mixed = background.copy()
    mixed[:, list(subset)] = point[list(subset)]
    return float(np.mean(predict(mixed)))


def shapley(
    predict: Callable[[np.ndarray], np.ndarray], point: Sequence[float], background: np.ndarray,
    names: Sequence[str] | None = None,
) -> dict[str, float]:  # fmt: skip
    """Each parameter's Shapley value at ``point`` against ``background``, exactly.

    Raises:
        ValueError: for more than ``MAX_DIMENSIONS`` parameters, or shapes that disagree.
    """
    point, background = (
        np.asarray(point, float),
        np.atleast_2d(np.asarray(background, float)),
    )
    d = point.size
    if d > MAX_DIMENSIONS or background.shape[1] != d:
        raise ValueError(
            f"shapley takes up to {MAX_DIMENSIONS} parameters, one per column"
        )
    names = list(names) if names is not None else [f"x{j}" for j in range(d)]
    cache = {
        subset: _value(predict, point, background, subset)
        for size in range(d + 1)
        for subset in combinations(range(d), size)
    }
    values = {}
    for j in range(d):
        others = [k for k in range(d) if k != j]
        total = 0.0
        for size in range(d):
            weight = factorial(size) * factorial(d - size - 1) / factorial(d)
            for subset in combinations(others, size):
                total += weight * (cache[tuple(sorted((*subset, j)))] - cache[subset])
        values[names[j]] = total
    return values
