"""Average treatment effects, with the variance reduction of common random numbers measured.

``treatment_effect(run, control, treated, output)`` estimates how much ``treated`` changes
``output`` against ``control``, over ``replicates`` pairs of runs. With common random numbers
replicate ``r`` of both arms gets the same seed, so each pair differs only by the treatment;
the estimate is also computed with independent seeds, on separate runs, and the ratio of the
two variances is reported: how many times fewer runs common random numbers need for the
same precision.

``counterfactual(recorder, step, change, until, output)`` asks the same question of one run
that has already happened: from the recorded state at ``step`` (``modelly.timetravel``), the
run is continued twice, once as it was and once with ``change`` applied, on the same random
streams, or on ``branches`` reseeded pairs.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from modelly.decide.compare import CONFIDENCE, Run, interval

STREAM_TREATED = 1  # spawn key of the independent arm's seeds


@dataclass(frozen=True)
class Effect:
    """An average effect and its interval.

    Attributes:
        mean, low, high: the mean difference (treated minus control) and its interval.
        paired_variance: the variance of the per-replicate differences (common numbers).
        independent_variance: the variance of the difference with independent seeds, or
            NaN when it was not measured.
        replicates: the number of pairs.
    """

    mean: float
    low: float
    high: float
    paired_variance: float
    independent_variance: float = float("nan")
    replicates: int = 0

    @property
    def variance_reduction(self) -> float:
        """How many times smaller the variance is with common random numbers."""
        return self.independent_variance / self.paired_variance


def _seeds(seed: int, replicates: int, key: int) -> list[int]:
    """Seeds of one arm: the stream ``key`` of ``seed``."""
    children = np.random.SeedSequence(seed, spawn_key=(key,)).spawn(replicates)
    return [int(child.generate_state(1)[0]) for child in children]


def treatment_effect(
    run: Run, control: Mapping[str, Any], treated: Mapping[str, Any], output: str, *,
    replicates: int = 30, seed: int = 0, confidence: float = CONFIDENCE,
    measure_independent: bool = True,
) -> Effect:  # fmt: skip
    """``treated`` minus ``control`` on ``output``, paired on common random numbers.

    With ``measure_independent`` the control runs are compared with treated runs on other
    seeds too, which doubles the cost and gives ``variance_reduction``.
    """
    seeds = _seeds(seed, replicates, 0)
    base = np.array([run(control, x)[output] for x in seeds], dtype=float)
    paired = np.array([run(treated, x)[output] for x in seeds], dtype=float) - base
    mean, low, high = interval(paired, confidence)
    independent = float("nan")
    if measure_independent:
        others = _seeds(seed, replicates, STREAM_TREATED)
        alone = np.array([run(treated, x)[output] for x in others], dtype=float)
        independent = float(alone.var(ddof=1) + base.var(ddof=1))
    return Effect(mean, low, high, float(paired.var(ddof=1)), independent, replicates)


def counterfactual(
    recorder: Any, step: float, change: Callable[[Any], None], until: float,
    output: Callable[[Any], float], *, branches: int = 1, confidence: float = CONFIDENCE,
) -> Effect:  # fmt: skip
    """The effect of ``change`` applied at ``step`` of a recorded run, read at ``until``.

    With one branch both continuations draw the same numbers as the recorded run; with
    several, pair ``i`` is reseeded from the run's seed (``Recorder.branch``), the same
    seeds for the changed and the unchanged continuation.
    """
    reseed = branches > 1
    as_was = recorder.branch(step, branches, reseed=reseed)
    changed = recorder.branch(step, branches, reseed=reseed)
    differences = []
    for before, after in zip(as_was, changed):
        change(after)
        before.run_until(until)
        after.run_until(until)
        differences.append(float(output(after)) - float(output(before)))
    values = np.array(differences)
    mean, low, high = interval(values, confidence)
    variance = float(values.var(ddof=1)) if values.size > 1 else 0.0
    return Effect(mean, low, high, variance, replicates=values.size)
