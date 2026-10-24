"""Matplotlib figures of a Posterior: marginals, pairs, and the fit to the data.

The figure is built with ``matplotlib.figure.Figure`` (no pyplot state), so it
works the same in scripts, notebooks and without a display; save it with
``figure.savefig(path)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from modelly._optional import require
from modelly.calibrate.posterior import weighted_quantile

if TYPE_CHECKING:
    from modelly.calibrate.posterior import Posterior

BINS = 20
POINT_SIZE = 8
ALPHA = 0.5
PANEL_INCHES = 2.4
OBSERVED_STYLE = {"color": "black", "marker": "o", "markersize": 3, "linestyle": "none"}


def _marginal(axis: Any, values: np.ndarray, weights: np.ndarray, name: str) -> None:
    """A weighted histogram of one parameter."""
    axis.hist(values, bins=BINS, weights=weights, color="tab:blue", alpha=ALPHA)
    axis.set_xlabel(name)
    axis.set_yticks([])


def _pairs(figure: Any, posterior: Posterior) -> None:
    """Histograms on the diagonal, weighted scatter plots below it."""
    numeric = posterior.numeric()
    names = list(numeric)
    axes = figure.subplots(len(names), len(names), squeeze=False)
    sizes = POINT_SIZE * posterior.weights / posterior.weights.max()
    for row, y_name in enumerate(names):
        for col, x_name in enumerate(names):
            axis = axes[row][col]
            if col > row:
                axis.set_axis_off()
            elif col == row:
                _marginal(axis, numeric[x_name], posterior.weights, x_name)
            else:
                axis.scatter(numeric[x_name], numeric[y_name], s=sizes, alpha=ALPHA)
                axis.set_xlabel(x_name)
                axis.set_ylabel(y_name)


def _fit(axis: Any, posterior: Posterior, target: Any, probability: float) -> None:
    """The observed values against the weighted median and band of the samples' fits."""
    simulated = posterior.summaries[target.name]
    tail = (1 - probability) / 2
    bands = [
        [weighted_quantile(column, posterior.weights, q) for column in simulated.T]
        for q in (tail, 0.5, 1 - tail)
    ]
    x = np.arange(len(target.observed))
    if target.summary is None:  # the observed series ends at the last step
        x = x + posterior.calibration.steps + 1 - len(target.observed)
        axis.set_xlabel("step")
    axis.fill_between(
        x, bands[0], bands[2], alpha=ALPHA, label=f"{probability:.0%} band"
    )
    axis.plot(x, bands[1], label="posterior median")
    axis.plot(x, target.observed, label="observed", **OBSERVED_STYLE)
    axis.set_title(target.name)
    axis.legend(fontsize="small")


def posterior_figure(posterior: Posterior, probability: float) -> Any:
    """The figure of :meth:`Posterior.plot`: pairs on the left, one fit per target on the right."""
    matplotlib_figure = require("matplotlib.figure", "viz")
    targets = posterior.calibration.targets
    count = max(len(posterior.numeric()), 1)
    width = PANEL_INCHES * (count + 1)
    height = PANEL_INCHES * max(count, len(targets))
    figure = matplotlib_figure.Figure(figsize=(width, height), layout="constrained")
    left, right = figure.subfigures(1, 2, width_ratios=[count, 1])
    if posterior.numeric():
        _pairs(left, posterior)
    for axis, target in zip(
        right.subplots(len(targets), 1, squeeze=False)[:, 0], targets
    ):
        _fit(axis, posterior, target, probability)
    return figure
