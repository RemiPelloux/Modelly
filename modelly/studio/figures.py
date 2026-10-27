"""Matplotlib figures of Studio's ensemble, assimilation and experiment views.

Plain functions of DataFrames, built on ``matplotlib.figure.Figure`` (no pyplot state), so
the views, their exports and a script share them:

- ``band_figure``: a band frame (``time``, ``quantity``, ``mean``, ``q<level>`` columns, as
  ``modelly.stream`` ensembles and filters return) with the observations on top;
- ``ess_figure`` and ``weights_figure``: a particle filter's effective sample size and its
  replicates' weights over time;
- ``trajectory_figure``: the parameters an ensemble Kalman filter adjusted, mean and spread;
- ``against_figure`` and ``series_figure``: an experiment's output against a parameter, and
  its runs step by step.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import pandas as pd
from matplotlib.figure import Figure

from modelly.stream.bands import quantile_column
from modelly.viz.palettes import OKABE_ITO

FIGSIZE = (6.0, 4.0)
PANEL_HEIGHT = 2.4
BAND_ALPHA = 0.25
POINT_SIZE = 12
OBSERVED = {"color": "black", "marker": "o", "s": POINT_SIZE, "zorder": 3}
MEDIAN_LEVEL = 0.5
SERIES_ALPHA = 0.6
# A shaded band needs a low and a high quantile.
MIN_BAND_LEVELS = 2
# A band frame's quantile columns: q0.05, q0.5, q0.95...
QUANTILE = re.compile(r"q(\d*\.?\d+(?:e-?\d+)?)")


def _colour(index: int) -> str:
    """The ``index``-th Okabe-Ito colour, cycling."""
    return OKABE_ITO[index % len(OKABE_ITO)]


def band_levels(bands: pd.DataFrame) -> list[float]:
    """The quantile levels a band frame has columns for, lowest first."""
    found = (QUANTILE.fullmatch(str(column)) for column in bands.columns)
    return sorted(float(match.group(1)) for match in found if match)


def _draw_band(axis, rows: pd.DataFrame, levels: Sequence[float], colour: str) -> None:
    """The outer quantiles as a shaded band, the median dashed, the mean as a line."""
    if len(levels) >= MIN_BAND_LEVELS:
        low, high = quantile_column(levels[0]), quantile_column(levels[-1])
        label = f"{levels[0]:g} to {levels[-1]:g}"
        axis.fill_between(
            rows["time"],
            rows[low],
            rows[high],
            color=colour,
            alpha=BAND_ALPHA,
            label=label,
        )
    if MEDIAN_LEVEL in levels:
        median = rows[quantile_column(MEDIAN_LEVEL)]
        axis.plot(rows["time"], median, color=colour, linestyle="--", label="median")
    axis.plot(rows["time"], rows["mean"], color=colour, label="mean")


def band_figure(
    bands: pd.DataFrame, observations: pd.DataFrame | None = None
) -> Figure | None:
    """One panel per quantity: its band over time, the observed values as dots.

    ``observations`` is long-format too (``time``, ``quantity``, ``value``). None when
    ``bands`` is empty.
    """
    if bands.empty:
        return None
    quantities = list(dict.fromkeys(bands["quantity"]))
    levels = band_levels(bands)
    height = max(FIGSIZE[1], PANEL_HEIGHT * len(quantities))
    figure = Figure(figsize=(FIGSIZE[0], height), layout="constrained")
    axes = figure.subplots(len(quantities), 1, squeeze=False, sharex=True)[:, 0]
    for index, (axis, name) in enumerate(zip(axes, quantities)):
        _draw_band(axis, bands[bands["quantity"] == name], levels, _colour(index))
        if observations is not None and not observations.empty:
            seen = observations[observations["quantity"] == name]
            axis.scatter(seen["time"], seen["value"], label="observed", **OBSERVED)
        axis.set_ylabel(str(name))
    axes[0].legend(loc="best", frameon=False, fontsize="small")
    axes[-1].set_xlabel("time")
    return figure


def ess_figure(history: pd.DataFrame, replicates: int, threshold: float) -> Figure:
    """The effective sample size at each observation, the resampling threshold dotted."""
    figure = Figure(figsize=FIGSIZE, layout="constrained")
    axis = figure.add_subplot()
    axis.plot(
        history["time"], history["ess"], marker="o", color=_colour(0), label="ESS"
    )
    axis.axhline(threshold * replicates, color="grey", linestyle=":", label="threshold")
    resampled = history[history["resampled"].astype(bool)]
    axis.scatter(
        resampled["time"], resampled["ess"], color="black", zorder=3, label="resampled"
    )
    axis.set_ylim(0, replicates)
    axis.set_xlabel("time")
    axis.set_ylabel("effective sample size")
    axis.legend(loc="best", frameon=False)
    return figure


def weights_figure(weights: pd.DataFrame) -> Figure:
    """Each replicate's weight at each observation, as a heat map (darker is heavier)."""
    figure = Figure(figsize=FIGSIZE, layout="constrained")
    axis = figure.add_subplot()
    times = list(weights.index)
    image = axis.imshow(
        weights.to_numpy().T, aspect="auto", origin="lower", cmap="Greys", vmin=0.0
    )
    axis.set_xticks(range(len(times)), [f"{t:g}" for t in times])
    axis.set_xlabel("observation time")
    axis.set_ylabel("replicate")
    figure.colorbar(image, ax=axis, label="weight")
    return figure


def trajectory_figure(history: pd.DataFrame, parameters: Sequence[str]) -> Figure:
    """Each adjusted parameter's ensemble mean over time, one standard deviation shaded."""
    count = max(len(parameters), 1)
    height = max(FIGSIZE[1], PANEL_HEIGHT * count)
    figure = Figure(figsize=(FIGSIZE[0], height), layout="constrained")
    axes = figure.subplots(count, 1, squeeze=False, sharex=True)[:, 0]
    for index, (axis, name) in enumerate(zip(axes, parameters)):
        mean, spread = history[name], history[f"{name}_sd"]
        colour = _colour(index)
        axis.fill_between(
            history["time"],
            mean - spread,
            mean + spread,
            color=colour,
            alpha=BAND_ALPHA,
        )
        axis.plot(history["time"], mean, color=colour, marker="o")
        axis.set_ylabel(name)
    axes[-1].set_xlabel("time")
    return figure


def against_figure(
    runs: pd.DataFrame, summary: pd.DataFrame, parameter: str, output: str
) -> Figure:
    """Every run's ``output`` against its ``parameter`` value, the mean per value on top."""
    figure = Figure(figsize=FIGSIZE, layout="constrained")
    axis = figure.add_subplot()
    axis.scatter(
        runs[parameter], runs[output], s=POINT_SIZE, color=_colour(0), label="runs"
    )
    axis.plot(
        summary[parameter], summary["mean"], color=_colour(1), marker="o", label="mean"
    )
    axis.set_xlabel(parameter)
    axis.set_ylabel(f"{output} (last step)")
    axis.legend(loc="best", frameon=False)
    return figure


def series_figure(series: pd.DataFrame, output: str) -> Figure:
    """One line per run: ``output`` step by step."""
    figure = Figure(figsize=FIGSIZE, layout="constrained")
    axis = figure.add_subplot()
    for index, column in enumerate(series.columns):
        axis.plot(
            series.index, series[column], color=_colour(index), alpha=SERIES_ALPHA
        )
    axis.set_xlabel("step")
    axis.set_ylabel(output)
    return figure


__all__ = [
    "against_figure",
    "band_figure",
    "band_levels",
    "ess_figure",
    "series_figure",
    "trajectory_figure",
    "weights_figure",
]
