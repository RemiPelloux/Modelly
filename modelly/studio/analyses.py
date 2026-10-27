"""Calibration posteriors and sensitivity results, as the Analysis tab shows them.

``modelly studio model.py:Model --analysis analysis.py:results`` names a function that
returns what to show: a ``modelly.calibrate.Posterior``, a
``modelly.sensitivity.SensitivityResult`` (Morris, Sobol, PAWN, OAT), or a list or dict of
them. The function runs once, when the tab first opens; it can load a saved calibration,
read a results store or run a quick analysis. From Python, append the objects to
``StudioSession.analyses``.

``view_of`` turns one object into what the tab draws: a title, its own figure (the
posterior's marginals, pairs and fits; the sensitivity method's plot) and a table (the
posterior summary with highest-density intervals; the ranked indices).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

from modelly.calibrate.posterior import Posterior
from modelly.sensitivity.results import SensitivityResult
from modelly.studio.loader import load_portrayal

POSTERIOR, SENSITIVITY = "posterior", "sensitivity"


@dataclass
class AnalysisView:
    """What the Analysis tab shows for one result."""

    title: str
    kind: str
    figure: Callable[[], Any]
    table: pd.DataFrame


def as_list(found: Any) -> list[tuple[str, Any]]:
    """``(name, result)`` pairs from one result, a list of them or a dict of them."""
    if isinstance(found, Mapping):
        return [(str(name), item) for name, item in found.items()]
    if isinstance(found, list | tuple):
        return [(f"result {index + 1}", item) for index, item in enumerate(found)]
    return [("result", found)]


def load_analyses(target: str) -> list[tuple[str, Any]]:
    """Call the function ``path/to/file.py:function`` names; its results, named.

    Raises:
        TargetError: When the function cannot be found.
    """
    return as_list(load_portrayal(target)())


def view_of(name: str, result: Any) -> AnalysisView:
    """The title, figure and table of a posterior or a sensitivity result.

    Raises:
        TypeError: For anything else.
    """
    if isinstance(result, Posterior):
        title = f"{name}: {result!r}"
        table = result.summary().rename_axis("parameter").reset_index()
        return AnalysisView(title, POSTERIOR, result.plot, table)
    if isinstance(result, SensitivityResult):
        title = f"{name}: {result.method}, ranked by {result.measure}"
        table = result.ranking().rename_axis("parameter").reset_index()
        return AnalysisView(title, SENSITIVITY, result.plot, table)
    raise TypeError(
        f"{name} is a {type(result).__name__}: the Analysis tab shows a "
        "modelly.calibrate.Posterior or a modelly.sensitivity result"
    )


__all__ = ["AnalysisView", "as_list", "load_analyses", "view_of"]
