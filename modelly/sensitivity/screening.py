"""Screening: one-at-a-time sweeps and Morris elementary effects.

Example:
    >>> from modelly.experiments import ScenarioSpace
    >>> space = ScenarioSpace(a=(0.0, 1.0), b=(0.0, 1.0))
    >>> screen = morris(lambda a, b: 4 * a + b, space, trajectories=4, seed=1)
    >>> list(screen.ranking().index)
    ['a', 'b']
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from modelly.calibrate.simulator import Stream
from modelly.experiments.space import Choice, ScenarioSpace
from modelly.sensitivity.results import PARAMETER, MorrisResult, OATResult
from modelly.sensitivity.study import Study

DEFAULT_LEVELS = 5
DEFAULT_TRAJECTORIES = 10
DEFAULT_MORRIS_LEVELS = 4
MIDPOINT = 0.5
OAT_KEY, MORRIS_KEY = 11, 12
TOLERANCE = 1e-12  # rounding slack when checking a step stays inside the cube


def _positions(dimension: Any, levels: int) -> list[float]:
    """Where a sweep evaluates a dimension: ``levels`` points, or the middle of each choice."""
    if isinstance(dimension, Choice):
        count = len(dimension.values)
        return [(k + MIDPOINT) / count for k in range(count)]
    return list(np.linspace(0.0, 1.0, levels))


def oat(
    model: Any,
    space: ScenarioSpace,
    output: Any = None,
    *,
    levels: int = DEFAULT_LEVELS,
    **settings: Any,
) -> OATResult:
    """Vary each parameter alone over ``levels`` values, the others at their midpoint.

    ``effect`` is the output's range along a parameter's sweep. ``settings`` are
    the :class:`~modelly.sensitivity.study.Study` fields (seed, steps,
    replicates, statistic, store, executor, max_parallel, options).
    """
    study = Study(model, space, output, **settings)
    rows, units = [], []
    for column, (name, dimension) in enumerate(space.dimensions.items()):
        for position in _positions(dimension, levels):
            unit = np.full(len(study.names), MIDPOINT)
            unit[column] = position
            units.append(unit)
            value = space.point(unit)[name]
            rows.append({PARAMETER: name, "position": position, "value": value})
    sweeps = pd.DataFrame(rows)
    sweeps["output"] = study.evaluate(np.vstack(units), OAT_KEY)
    grouped = sweeps.groupby(PARAMETER, sort=False)["output"]
    table = pd.DataFrame({"low": grouped.min(), "high": grouped.max()})
    table["effect"] = table["high"] - table["low"]
    info = {"evaluations": len(sweeps), "levels": levels}
    return OATResult("oat", table.rename_axis(None), "effect", info, sweeps)


def morris_design(
    dimensions: int, count: int, levels: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Morris trajectories on a ``levels`` grid.

    Returns the points ``[trajectory, step, dimension]`` (``dimensions + 1``
    steps), the factor each step moves ``[trajectory, step]`` and its signed
    size ``[trajectory, step]``.
    """
    delta = levels / (2 * (levels - 1))
    grid = np.arange(levels) / (levels - 1)
    points = np.empty((count, dimensions + 1, dimensions))
    moved = np.empty((count, dimensions), dtype=int)
    steps = np.empty((count, dimensions))
    for t in range(count):
        x = rng.choice(grid, size=dimensions)
        points[t, 0] = x
        moved[t] = rng.permutation(dimensions)
        for k, factor in enumerate(moved[t]):
            step = delta if x[factor] + delta <= 1 + TOLERANCE else -delta
            x = x.copy()
            x[factor] = x[factor] + step
            points[t, k + 1], steps[t, k] = x, step
    return points, moved, steps


def morris(
    model: Any,
    space: ScenarioSpace,
    output: Any = None,
    *,
    trajectories: int = DEFAULT_TRAJECTORIES,
    levels: int = DEFAULT_MORRIS_LEVELS,
    **settings: Any,
) -> MorrisResult:
    """Morris elementary effects: ``mu``, ``mu_star`` (ranking) and ``sigma`` per parameter.

    ``trajectories`` random trajectories on a
    ``levels`` grid, drawn from the stream ``(DESIGN, MORRIS_KEY)`` of the
    seed: ``trajectories * (parameters + 1)`` evaluations. ``settings`` are the
    :class:`~modelly.sensitivity.study.Study` fields.
    """
    count = trajectories
    if count < 2 or levels < 2:
        raise ValueError("morris needs at least 2 trajectories and 2 levels")
    study = Study(model, space, output, **settings)
    d = len(study.names)
    points, moved, steps = morris_design(
        d, count, levels, study.rng(Stream.DESIGN, MORRIS_KEY)
    )
    values = study.evaluate(points.reshape(-1, d), MORRIS_KEY).reshape(count, d + 1)
    effects = np.empty((count, d))
    for t in range(count):
        effects[t, moved[t]] = np.diff(values[t]) / steps[t]
    table = pd.DataFrame(
        {
            "mu": effects.mean(axis=0),
            "mu_star": np.abs(effects).mean(axis=0),
            "sigma": effects.std(axis=0, ddof=1),
        },
        index=study.names,
    )
    info = {"trajectories": count, "levels": levels, "evaluations": values.size}
    return MorrisResult("morris", table, "mu_star", info)
