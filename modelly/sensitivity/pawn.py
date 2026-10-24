"""PAWN: moment-independent sensitivity from output distributions (Pianosi and Wagener, 2015).

One Latin-hypercube sample of ``samples`` points is evaluated. For each
parameter its range is cut into ``slices`` equal-count slices; in each slice
the distribution of the output is compared with the unconditional one by the
Kolmogorov-Smirnov statistic (the largest gap between the two CDFs). A
parameter's index summarises its slices' statistics (``median``, ``mean``,
``max``); 0 means the output's distribution does not change with it. Suits
skewed or multi-modal outputs, where variance-based indices mislead.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from modelly.calibrate.simulator import Stream
from modelly.experiments.space import ScenarioSpace
from modelly.sensitivity.results import SensitivityResult
from modelly.sensitivity.study import Study

DEFAULT_SAMPLES = 500
DEFAULT_SLICES = 10
PAWN_KEY = 14
SUMMARIES = ("median", "mean", "max")


def ks_statistics(column: np.ndarray, output: np.ndarray, slices: int) -> np.ndarray:
    """The KS statistic of each slice of ``column`` against the whole ``output``."""
    from scipy.stats import ks_2samp  # noqa: PLC0415 - lazy import

    order = np.argsort(column, kind="stable")
    parts = np.array_split(order, slices)
    return np.array([ks_2samp(output[part], output).statistic for part in parts])


def pawn(
    model: Any,
    space: ScenarioSpace,
    output: Any = None,
    *,
    samples: int = DEFAULT_SAMPLES,
    slices: int = DEFAULT_SLICES,
    summary: str = "median",
    **settings: Any,
) -> SensitivityResult:
    """PAWN indices (``median``, ``mean`` and ``max`` KS statistic) per parameter.

    ``summary`` picks the column ``ranking`` sorts by. ``settings`` are the
    :class:`~modelly.sensitivity.study.Study` fields.
    """
    from scipy.stats import qmc  # noqa: PLC0415 - lazy import

    if summary not in SUMMARIES:
        raise ValueError(f"summary must be one of {SUMMARIES}, got {summary!r}")
    if not 2 <= slices <= samples // 2:
        raise ValueError("need 2 <= slices <= samples / 2")
    study = Study(model, space, output, **settings)
    rng = study.rng(Stream.DESIGN, PAWN_KEY)
    units = qmc.LatinHypercube(len(study.names), rng=rng).random(samples)
    values = study.evaluate(units, PAWN_KEY)
    rows = {}
    for column, name in enumerate(study.names):
        statistics = ks_statistics(units[:, column], values, slices)
        rows[name] = {key: float(getattr(np, key)(statistics)) for key in SUMMARIES}
    table = pd.DataFrame.from_dict(rows, orient="index")
    info = {"samples": samples, "slices": slices, "evaluations": samples}
    return SensitivityResult("pawn", table, summary, info)
