"""Browse an experiment's results store: its runs, filtered by parameters, one output against one.

``ExperimentBrowser(path)`` opens the folder an ``Experiment`` wrote (``experiment.json``
and one Parquet file per run, see ``modelly.experiments.store``). ``runs()`` has one row per
finished run: its keys, its parameters and its outputs at its last step. ``select`` keeps
the runs whose parameters fall in a range or a set of values; ``against`` summarises an
output over the runs at each value of a parameter, which the Experiments tab plots; and
``series`` gives the selected runs' outputs step by step.

Needs the ``experiments`` extra (pyarrow and DuckDB), like the store itself.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from modelly.experiments.store import METADATA, RESERVED, STEP, VIEW, ResultsStore

# A run's last row: the one with the highest step of its run_id.
LAST_ROWS = (
    f"SELECT * FROM {VIEW} QUALIFY row_number() OVER "  # noqa: S608 (constants only)
    f"(PARTITION BY run_id ORDER BY {STEP} DESC) = 1 ORDER BY point, replicate"
)
SUMMARY = ("mean", "min", "max", "count")

Selection = Mapping[str, tuple[float, float] | Sequence[Any]]


def _fingerprint(path: Path) -> dict[str, Any]:
    """The store's ``experiment.json``, or ``{}`` when it has none."""
    metadata = path / METADATA
    if not metadata.is_file():
        return {}
    return json.loads(metadata.read_text(encoding="utf-8"))


def _keep(column: pd.Series, allowed: tuple[float, float] | Sequence[Any]) -> pd.Series:
    """Which rows of ``column`` a range ``(low, high)`` or a list of values allows."""
    if isinstance(allowed, tuple):
        low, high = allowed
        return column.between(low, high)
    return column.isin(list(allowed))


class ExperimentBrowser:
    """The runs of one results store, for the Experiments tab.

    Args:
        path: The store folder.

    Raises:
        LookupError: When the folder holds no finished run.
    """

    def __init__(self, path: str | Path) -> None:
        """Open the store's runs as a DuckDB view."""
        self.path = Path(path)
        self.results = ResultsStore(self.path).results()
        fingerprint = _fingerprint(self.path)
        self.model = fingerprint.get("model")
        columns = list(self.results.query(f"SELECT * FROM {VIEW} LIMIT 0").columns)  # noqa: S608
        points = fingerprint.get("points") or []
        named = {name for point in points for name in point}
        self.parameters = [c for c in columns if c in named]
        others = [c for c in columns if c not in RESERVED and c not in named]
        self.outputs = list(fingerprint.get("outputs") or others)

    def runs(self) -> pd.DataFrame:
        """One row per finished run: keys, parameters and the outputs at its last step."""
        return self.results.query(LAST_ROWS).df()

    def select(self, selection: Selection | None = None) -> pd.DataFrame:
        """The runs whose parameters ``selection`` allows.

        ``selection`` maps a parameter to a ``(low, high)`` range (both ends kept) or to
        a list of the values to keep; parameters it does not name are not filtered.

        Raises:
            KeyError: When it names a column the runs do not have.
        """
        runs = self.runs()
        keep = pd.Series(True, index=runs.index)
        for name, allowed in (selection or {}).items():
            keep &= _keep(runs[name], allowed)
        return runs[keep].reset_index(drop=True)

    def against(
        self, parameter: str, output: str, runs: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        """``output`` at the runs' last step, summarised at each value of ``parameter``.

        One row per value, sorted, with the mean, min, max and count over the runs (all
        of them unless ``runs``, a selection, is given).
        """
        runs = self.runs() if runs is None else runs
        grouped = runs.groupby(parameter)[output].agg(list(SUMMARY))
        return grouped.reset_index().sort_values(parameter, kind="stable")

    def series(self, output: str, run_ids: Sequence[str] | None = None) -> pd.DataFrame:
        """``output`` step by step, one column per run (all runs unless ``run_ids``)."""
        frame = self.results.df()
        if run_ids is not None:
            frame = frame[frame["run_id"].isin(list(run_ids))]
        return frame.pivot_table(index=STEP, columns="run_id", values=output)

    def describe(self) -> str:
        """A line for the tab: the model, the run count, the parameters and the outputs."""
        count = len(self.runs())
        return (
            f"{self.model or 'experiment'}: {count} run(s); parameters "
            f"{', '.join(self.parameters) or 'none'}; outputs {', '.join(self.outputs)}"
        )


__all__ = ["ExperimentBrowser", "Selection"]
