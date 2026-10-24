"""Results of a sensitivity analysis: a table per parameter, a ranking and a plot.

Every method returns a :class:`SensitivityResult` (or a subclass) whose
``table`` has one row per parameter. ``ranking()`` sorts it by the method's
main measure, most influential first; ``to_dataframe()`` returns a copy;
``plot()`` draws a Matplotlib figure (``figure.savefig(path)`` writes it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from modelly._optional import require

PANEL_INCHES = (6.0, 3.5)
BAR_WIDTH = 0.4
PARAMETER = "parameter"


def _figure(size: tuple[float, float] = PANEL_INCHES) -> tuple[Any, Any]:
    """A Matplotlib figure (no pyplot state) and its single axis."""
    matplotlib_figure = require("matplotlib.figure", "viz")
    figure = matplotlib_figure.Figure(figsize=size, layout="constrained")
    return figure, figure.subplots()


@dataclass(repr=False)
class SensitivityResult:
    """One analysis: ``table`` (index: parameter) and the measure ranking uses.

    Attributes:
        method: the method's name.
        table: one row per parameter.
        measure: the column ``ranking`` sorts by.
        info: how the analysis ran (samples, model runs, seed...).
    """

    method: str
    table: pd.DataFrame
    measure: str
    info: dict[str, Any] = field(default_factory=dict)

    def ranking(self) -> pd.DataFrame:
        """The table sorted by the main measure, most influential first."""
        return self.table.sort_values(self.measure, ascending=False, kind="stable")

    def to_dataframe(self) -> pd.DataFrame:
        """A copy of the table, the parameter as a column."""
        return self.table.rename_axis(PARAMETER).reset_index()

    def plot(self) -> Any:
        """A bar chart of the main measure, parameters in ranking order."""
        ranked = self.ranking()
        figure, axis = _figure()
        axis.bar(ranked.index, ranked[self.measure])
        axis.set_ylabel(self.measure)
        axis.set_title(self.method)
        return figure

    def __repr__(self) -> str:
        """The method and the ranked parameters."""
        return f"{type(self).__name__}({self.method}, {list(self.ranking().index)})"


class MorrisResult(SensitivityResult):
    """Morris screening: ``mu``, ``mu_star`` and ``sigma`` of the elementary effects."""

    def plot(self) -> Any:
        """``sigma`` against ``mu_star``: far right is influential, high is non-linear."""
        figure, axis = _figure()
        axis.scatter(self.table["mu_star"], self.table["sigma"])
        for name, row in self.table.iterrows():
            axis.annotate(str(name), (row["mu_star"], row["sigma"]))
        axis.set_xlabel("mu* (mean absolute effect)")
        axis.set_ylabel("sigma (interactions, non-linearity)")
        return figure


class SobolResult(SensitivityResult):
    """Sobol indices ``S1`` and ``ST`` with bootstrap intervals."""

    def plot(self) -> Any:
        """First-order and total indices side by side, with their intervals."""
        figure, axis = _figure()
        positions = range(len(self.table))
        for offset, index in ((-BAR_WIDTH / 2, "S1"), (BAR_WIDTH / 2, "ST")):
            values = self.table[index]
            error = [
                values - self.table[f"{index}_low"],
                self.table[f"{index}_high"] - values,
            ]
            axis.bar(
                [p + offset for p in positions],
                values,
                BAR_WIDTH,
                yerr=error,
                label=index,
            )
        axis.set_xticks(list(positions), list(self.table.index))
        axis.set_ylabel("Sobol index")
        axis.legend()
        return figure


@dataclass(repr=False)
class OATResult(SensitivityResult):
    """One-at-a-time sweeps: ``sweeps`` holds every evaluated value."""

    sweeps: pd.DataFrame = field(default_factory=pd.DataFrame)

    def plot(self) -> Any:
        """The output along each parameter's sweep, the others at their midpoint."""
        figure, axis = _figure()
        for name, sweep in self.sweeps.groupby(PARAMETER, sort=False):
            axis.plot(sweep["position"], sweep["output"], marker="o", label=str(name))
        axis.set_xlabel("position in the parameter's range (0 to 1)")
        axis.set_ylabel("output")
        axis.legend()
        return figure
