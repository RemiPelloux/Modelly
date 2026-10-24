"""Variance-based sensitivity: first-order and total Sobol indices.

Saltelli sampling: two independent matrices ``A`` and ``B`` of ``samples``
rows each come from one scrambled Sobol sequence of twice the dimension
(``scipy.stats.qmc``, scrambled from the seed), and ``AB_i`` is ``A`` with
column ``i`` taken from ``B``: ``samples * (parameters + 2)`` evaluations.

Estimators (Saltelli et al., 2010), with ``V`` the variance of ``f(A)`` and ``f(B)``:

=============  ============================================  ==========================================
``estimator``  S1                                            ST
=============  ============================================  ==========================================
``jansen``     ``(V - mean((f(B) - f(AB_i))**2) / 2) / V``   ``mean((f(A) - f(AB_i))**2) / 2 / V``
``saltelli``   ``mean(f(B) * (f(AB_i) - f(A))) / V``         ``mean(f(A) * (f(A) - f(AB_i))) / V``
=============  ============================================  ==========================================

Confidence intervals come from resampling the rows ``bootstrap`` times (the
stream ``(BOOTSTRAP, SOBOL_KEY)`` of the seed) and taking percentiles.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from modelly.calibrate.simulator import Stream
from modelly.experiments.space import ScenarioSpace
from modelly.sensitivity.results import SobolResult
from modelly.sensitivity.study import Study

DEFAULT_SAMPLES = 1024
DEFAULT_BOOTSTRAP = 200
DEFAULT_CONFIDENCE = 0.95
ESTIMATORS = ("jansen", "saltelli")
SOBOL_KEY = 13
PERCENT = 100


def saltelli_sample(
    dimensions: int, samples: int, rng: np.random.Generator
) -> np.ndarray:
    """The points ``[A; B; AB_1; ...; AB_d]`` in the unit cube."""
    from scipy.stats import qmc  # noqa: PLC0415 - lazy import

    base = qmc.Sobol(2 * dimensions, scramble=True, rng=rng).random(samples)
    a, b = base[:, :dimensions], base[:, dimensions:]
    blocks = [a, b]
    for i in range(dimensions):
        mixed = a.copy()
        mixed[:, i] = b[:, i]
        blocks.append(mixed)
    return np.vstack(blocks)


def indices(
    f_a: np.ndarray, f_b: np.ndarray, f_ab: np.ndarray, estimator: str
) -> tuple[np.ndarray, np.ndarray]:
    """S1 and ST from ``f(A)``, ``f(B)`` and ``f(AB)[parameter, row]``."""
    variance = np.var(np.concatenate([f_a, f_b]))
    if variance == 0:
        return np.zeros(len(f_ab)), np.zeros(len(f_ab))
    if estimator == "jansen":
        first = (variance - 0.5 * np.mean((f_b - f_ab) ** 2, axis=1)) / variance
        total = 0.5 * np.mean((f_a - f_ab) ** 2, axis=1) / variance
        return first, total
    first = np.mean(f_b * (f_ab - f_a), axis=1) / variance
    total = np.mean(f_a * (f_a - f_ab), axis=1) / variance
    return first, total


def _bootstrap(
    values: tuple[np.ndarray, np.ndarray, np.ndarray],
    estimator: str,
    resamples: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """S1 and ST of ``resamples`` row resamples: ``[resample, parameter]`` each."""
    f_a, f_b, f_ab = values
    rows = len(f_a)
    firsts, totals = [], []
    for _ in range(resamples):
        pick = rng.integers(0, rows, rows)
        first, total = indices(f_a[pick], f_b[pick], f_ab[:, pick], estimator)
        firsts.append(first)
        totals.append(total)
    return np.array(firsts), np.array(totals)


def sobol(
    model: Any,
    space: ScenarioSpace,
    output: Any = None,
    *,
    samples: int = DEFAULT_SAMPLES,
    bootstrap: int = DEFAULT_BOOTSTRAP,
    confidence: float = DEFAULT_CONFIDENCE,
    estimator: str = "jansen",
    **settings: Any,
) -> SobolResult:
    """First-order (``S1``) and total (``ST``) Sobol indices with bootstrap intervals.

    ``samples`` should be a power of two. ``settings`` are the
    :class:`~modelly.sensitivity.study.Study` fields (seed, steps, replicates,
    statistic, store, executor, max_parallel, options).
    """
    if estimator not in ESTIMATORS:
        raise ValueError(f"estimator must be one of {ESTIMATORS}, got {estimator!r}")
    if bootstrap < 1 or not 0 < confidence < 1:
        raise ValueError("bootstrap >= 1 and 0 < confidence < 1 are required")
    study = Study(model, space, output, **settings)
    d = len(study.names)
    units = saltelli_sample(d, samples, study.rng(Stream.DESIGN, SOBOL_KEY))
    blocks = study.evaluate(units, SOBOL_KEY).reshape(d + 2, samples)
    values = (blocks[0], blocks[1], blocks[2:])
    first, total = indices(*values, estimator)
    rng = study.rng(Stream.BOOTSTRAP, SOBOL_KEY)
    firsts, totals = _bootstrap(values, estimator, bootstrap, rng)
    tails = (PERCENT * (1 - confidence) / 2, PERCENT * (1 + confidence) / 2)
    table = pd.DataFrame({"S1": first, "ST": total}, index=study.names)
    for name, draws in (("S1", firsts), ("ST", totals)):
        table[f"{name}_low"], table[f"{name}_high"] = np.percentile(
            draws, tails, axis=0
        )
    info = {"samples": samples, "evaluations": units.shape[0], "estimator": estimator}
    info |= {"bootstrap": bootstrap, "confidence": confidence}
    return SobolResult("sobol", table, "ST", info)
