"""Combinatorial optimisation: choose whole records from a sample to match census totals.

IPF fits a table of people; it cannot keep the members of a household together. The
combinatorial-optimisation approach does: draw ``size`` records (households, each with
its members' counts) from a sample, with replacement, and swap one drawn record for
another while that brings the totals closer to the targets. ``anneal`` does it by
simulated annealing: a swap that worsens the total absolute error ``TAE`` by ``d`` is
still taken with probability ``exp(-d / T)``, where the temperature ``T`` falls
geometrically, so the search can leave local optima early and settles at the end.

The sample is yours: a public-use microdata sample, a survey, or a synthetic sample.
Modelly bundles no microdata.

References:
    Williamson, P., Birkin, M. and Rees, P. H. (1998). The estimation of population
    microdata by using data from small area statistics and samples of anonymised
    records. Environment and Planning A, 30(5), 785-816.

    Harland, K., Heppenstall, A., Smith, D. and Birkin, M. (2012). Creating realistic
    synthetic populations at varying spatial scales: a comparative critique of population
    synthesis techniques. Journal of Artificial Societies and Social Simulation, 15(1), 1.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

ITERATIONS = 20_000
TEMPERATURE = 1.0
COOLING = 0.9995


@dataclass(frozen=True)
class Annealing:
    """One simulated-annealing run: how many records to draw and the cooling schedule.

    Attributes:
        size: the number of records to draw (the region's households, say).
        iterations: the most swaps tried; the run stops early at a perfect fit.
        temperature: the starting temperature, in units of the targets (people).
        cooling: the factor applied to the temperature after every swap tried.
    """

    size: int
    iterations: int = ITERATIONS
    temperature: float = TEMPERATURE
    cooling: float = COOLING


def total_absolute_error(
    sample: pd.DataFrame, selection: np.ndarray, targets: Mapping[str, float]
) -> float:
    """``sum(|total of the selected records - target|)`` over the target columns.

    Args:
        sample: one row per record, with one numeric column per target.
        selection: row positions of the selected records (repeats allowed).
        targets: column name to its target total.
    """
    values = sample[list(targets)].to_numpy(dtype=float)
    totals = values[np.asarray(selection, dtype=np.intp)].sum(axis=0)
    return float(np.abs(totals - np.fromiter(targets.values(), dtype=float)).sum())


def anneal(
    sample: pd.DataFrame,
    targets: Mapping[str, float],
    settings: Annealing,
    rng: np.random.Generator,
) -> np.ndarray:
    """Row positions of ``settings.size`` records of ``sample`` whose totals fit ``targets``.

    Args:
        sample: one row per record, with one numeric column per target (for a
            household: its children, adults, seniors, a one-hot of its size, ...).
        targets: column name to its target total in the region.
        settings: the number of records and the cooling schedule.
        rng: a numpy generator (``model.rng``): the start and every swap.

    Returns:
        an ``intp`` array of ``settings.size`` row positions, with repeats.
    """
    values = sample[list(targets)].to_numpy(dtype=float)
    goal = np.fromiter(targets.values(), dtype=float)
    selection = rng.integers(len(values), size=settings.size)
    slots = rng.integers(settings.size, size=settings.iterations)
    swaps = rng.integers(len(values), size=settings.iterations)
    chances = rng.random(settings.iterations)
    totals = values[selection].sum(axis=0)
    error = float(np.abs(totals - goal).sum())
    temperature = settings.temperature
    for slot, swap, chance in zip(slots, swaps, chances):
        if error == 0.0:
            break
        trial = totals - values[selection[slot]] + values[swap]
        trial_error = float(np.abs(trial - goal).sum())
        worse = trial_error - error
        if worse <= 0.0 or chance < math.exp(-worse / temperature):
            selection[slot], totals, error = swap, trial, trial_error
        temperature *= settings.cooling
    return selection.astype(np.intp)
