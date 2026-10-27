"""Synthetic populations from census-style marginals, by iterative proportional fitting.

Census tables usually give, per region, the count of people in each level of each
attribute (age band, sex, household size) but not the joint table. ``ipf`` fits a joint
table to those marginals, starting from a ``seed`` (a microsample cross-tabulation, or
ones), and ``synthesize_population`` turns the fitted tables into one row per person,
ready to create one agent per row.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

TOLERANCE = 1e-10
MAX_ITERATIONS = 1000
REGION = "region"


def ipf(
    seed: np.ndarray,
    marginals: Sequence[Sequence[float]],
    tolerance: float = TOLERANCE,
    max_iterations: int = MAX_ITERATIONS,
) -> np.ndarray:
    """Fit a table to its one-dimensional marginals by iterative proportional fitting.

    Args:
        seed: the starting table, one axis per attribute; its zeros stay zero.
        marginals: the target totals along each axis, in axis order; all sum to the same total.
        tolerance: stop when no marginal is off by more than ``tolerance`` times the total.
        max_iterations: the most fitting rounds.

    Returns:
        the fitted table, of the shape of ``seed``.
    """
    table = np.array(seed, dtype=float)
    targets = [np.asarray(m, dtype=float) for m in marginals]
    _check_marginals(table, targets)
    total = targets[0].sum()
    for _ in range(max_iterations):
        for axis, target in enumerate(targets):
            current = _margin(table, axis)
            factor = np.divide(
                target, current, out=np.zeros_like(target), where=current > 0
            )
            shape = [1] * table.ndim
            shape[axis] = -1
            table *= factor.reshape(shape)
        worst = max(np.abs(_margin(table, a) - t).max() for a, t in enumerate(targets))
        if worst <= tolerance * max(total, 1.0):
            break
    return table


def synthesize_population(
    categories: Mapping[str, Sequence[Any]],
    marginals: Mapping[Any, Mapping[str, Sequence[float]]],
    rng: np.random.Generator,
    seed: np.ndarray | None = None,
) -> pd.DataFrame:
    """One row per synthetic person, with a ``region`` column and one column per attribute.

    Args:
        categories: attribute name to its levels, for example ``{"age": ["0-17", "18+"]}``.
        marginals: region label to, per attribute, the count of people at each level.
        rng: a numpy generator (``model.rng``) to round fitted counts to whole people.
        seed: the starting joint table (shape: one axis per attribute); defaults to ones.

    Returns:
        a DataFrame. The fitted table is rounded to whole people at random, one level of
        the first attribute at a time (floors, then the remainder drawn in proportion to
        the fractional parts). With whole-number marginals every region gets exactly its
        total and its first attribute's counts; the other marginals are met in
        expectation, each count off by less than the number of first-attribute levels.
    """
    names = list(categories)
    shape = tuple(len(categories[name]) for name in names)
    seed = np.ones(shape) if seed is None else np.asarray(seed, dtype=float)
    frames = []
    for region, margins in marginals.items():
        fitted = ipf(seed, [margins[name] for name in names])
        counts = np.concatenate([_integerise(part.ravel(), rng) for part in fitted])
        # repeat takes intp counts: int32 on 32-bit platforms (Pyodide, wasm32).
        repeats = counts.astype(np.intp)
        cells = np.unravel_index(np.repeat(np.arange(counts.size), repeats), shape)
        columns = {
            name: np.asarray(categories[name], dtype=object)[idx]
            for name, idx in zip(names, cells)
        }
        frame = pd.DataFrame(columns)
        frame.insert(0, REGION, region)
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=[REGION, *names])
    return pd.concat(frames, ignore_index=True)


def _margin(table: np.ndarray, axis: int) -> np.ndarray:
    """The totals of ``table`` along ``axis``."""
    others = tuple(a for a in range(table.ndim) if a != axis)
    return table.sum(axis=others)


def _check_marginals(table: np.ndarray, targets: list[np.ndarray]) -> None:
    """Reject marginals that do not match the table's shape or each other's total."""
    if len(targets) != table.ndim:
        raise ValueError(f"Expected {table.ndim} marginals, got {len(targets)}.")
    for axis, target in enumerate(targets):
        if target.shape != (table.shape[axis],):
            raise ValueError(
                f"Marginal {axis} has {target.size} levels; the table has {table.shape[axis]}."
            )
    totals = np.array([t.sum() for t in targets])
    if not np.allclose(totals, totals[0]):
        raise ValueError(f"Marginals must share one total, got {totals.tolist()}.")


def _integerise(expected: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Whole counts with the same total: floors, then the remainder by fractional part."""
    counts = np.floor(expected).astype(np.int64)
    fractions = expected - counts
    remainder = round(float(expected.sum())) - int(counts.sum())
    if remainder > 0:
        chosen = rng.choice(
            expected.size, size=remainder, replace=False, p=fractions / fractions.sum()
        )
        counts[chosen] += 1
    return counts
