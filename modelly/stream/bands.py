"""Quantile bands across an ensemble, as plain DataFrames.

A band is the spread of the observed quantities across replicates at a time:
the (weighted) mean and a few quantiles. Rows are long-format, one per time
and quantity, so a plot, a table or a live view (Studio) reads them without
knowing anything about ensembles::

    time  quantity  mean   q0.05  q0.5   q0.95
    12.0  cases     41.3   30.0   40.5   55.2

Weighted quantiles put each replicate's weight at the midpoint of its step in
the cumulative weights and interpolate linearly between them; with equal
weights this is the Hazen definition (Hyndman & Fan 1996, definition 5).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from modelly.core.checkpoint import checkpoint_bytes, model_from_bytes

if TYPE_CHECKING:
    from modelly.core.model import Model
    from modelly.stream.operators import ObservationOperator

DEFAULT_QUANTILES = (0.05, 0.5, 0.95)
HALF = 0.5
KEYS = ("time", "quantity", "mean")


def quantile_column(level: float) -> str:
    """The column of quantile ``level``: ``q0.05``, ``q0.5``, ..."""
    return f"q{level:g}"


def _normalised(weights: Sequence[float] | None, n: int) -> np.ndarray:
    """``weights`` scaled to sum to one; equal weights when ``None``."""
    if weights is None:
        return np.full(n, 1.0 / n)
    array = np.asarray(weights, dtype=float)
    if array.shape != (n,) or np.any(array < 0) or not array.sum() > 0:
        raise ValueError(f"weights must be {n} non-negative numbers, not all zero")
    return array / array.sum()


def weighted_quantiles(
    values: Sequence[float],
    weights: Sequence[float] | None,
    quantiles: Sequence[float],
) -> np.ndarray:
    """Quantiles of ``values`` weighted by ``weights`` (equal when ``None``)."""
    data = np.asarray(values, dtype=float)
    share = _normalised(weights, len(data))
    held = share > 0  # a replicate without weight is not part of the distribution
    data, share = data[held], share[held]
    order = np.argsort(data, kind="stable")
    sorted_values, sorted_share = data[order], share[order]
    positions = np.cumsum(sorted_share) - HALF * sorted_share
    return np.interp(quantiles, positions, sorted_values)


def _band_rows(
    time: float,
    names: Sequence[str],
    values: np.ndarray,
    weights: Sequence[float] | None,
    quantiles: Sequence[float],
) -> list[dict[str, Any]]:
    """One band row per quantity; ``values`` has a column per quantity."""
    share = _normalised(weights, len(values))
    rows = []
    for column, name in enumerate(names):
        series = values[:, column]
        levels = weighted_quantiles(series, share, quantiles)
        row = {"time": float(time), "quantity": name, "mean": float(share @ series)}
        row.update({quantile_column(q): float(v) for q, v in zip(quantiles, levels)})
        rows.append(row)
    return rows


def _band_frame(rows: list[dict[str, Any]], quantiles: Sequence[float]) -> pd.DataFrame:
    """Band rows as a DataFrame with the band columns in order, even when empty."""
    columns = [*KEYS, *(quantile_column(q) for q in quantiles)]
    return pd.DataFrame(rows, columns=columns)


def _forecast_times(start: float, until: float, every: float) -> list[float]:
    """``start``, then every ``every`` time units, ending exactly at ``until``."""
    if every <= 0:
        raise ValueError(f"every must be positive, got {every}")
    if until < start:
        raise ValueError(f"cannot forecast back to {until} from time {start}")
    times = [start]
    step = 1
    while start + step * every < until:
        times.append(start + step * every)
        step += 1
    if until > start:
        times.append(until)
    return times


def forecast_band(
    models: Sequence[Model],
    operator: ObservationOperator,
    until: float,
    *,
    every: float = 1.0,
    quantiles: Sequence[float] = DEFAULT_QUANTILES,
    weights: Sequence[float] | None = None,
) -> pd.DataFrame:
    """Run checkpoint copies of ``models`` to ``until``, a band at every forecast time.

    The times are the models' current time, then every ``every`` time units,
    ending exactly at ``until``; ``models`` themselves do not move.
    """
    copies = [model_from_bytes(checkpoint_bytes(m), "forecast") for m in models]
    rows: list[dict[str, Any]] = []
    for time in _forecast_times(copies[0].time, until, every):
        for copy in copies:
            if time > copy.time:
                copy.run_until(time)
        values = np.array([list(operator(c).values()) for c in copies], dtype=float)
        rows.extend(_band_rows(time, operator.names, values, weights, quantiles))
    return _band_frame(rows, quantiles)
