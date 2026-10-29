"""The Experiments and Analysis tabs: a results store, posteriors and sensitivity results."""

from __future__ import annotations

from typing import Any

import pandas as pd
import solara

from modelly.studio.analyses import load_analyses, view_of
from modelly.studio.browser import ExperimentBrowser
from modelly.studio.figures import against_figure, series_figure
from modelly.studio.state import StudioState

# A parameter with more distinct values than this is filtered by a range.
MAX_CHOICES = 12
RANGE_STEPS = 100
SERIES_RUNS = 50
EXPERIMENTS_HELP = (
    "Start Studio with `--results path/to/store` (the folder an `Experiment` wrote) to "
    "browse its runs: filter them by parameters, plot an output against a parameter."
)
ANALYSIS_HELP = (
    "Start Studio with `--analysis file.py:function`, a function returning a calibration "
    "`Posterior` or a sensitivity result (or a list or dict of them), to see their plots "
    "here; from Python, append `(name, result)` to `session.analyses`."
)


def open_store(path: str) -> tuple[ExperimentBrowser | None, str | None]:
    """The browser of the store at ``path``, or None and why it cannot be opened."""
    try:
        return ExperimentBrowser(path), None
    except (LookupError, OSError, ImportError) as error:
        return None, f"cannot open the results store {path}: {error}"


def _numeric_range(column: pd.Series) -> bool:
    """Whether ``column`` is numbers with too many values to pick one by one."""
    numeric = pd.api.types.is_numeric_dtype(column) and column.dtype != bool
    return numeric and column.nunique() > MAX_CHOICES


def _filter(name: str, column: pd.Series, selection) -> None:
    """A range slider or a multiple select for one parameter."""

    def keep(allowed: Any) -> None:
        selection.set({**selection.value, name: allowed})

    if _numeric_range(column):
        low, high = float(column.min()), float(column.max())
        solara.SliderRangeFloat(
            name,
            value=selection.value.get(name, (low, high)),
            min=low,
            max=high,
            step=(high - low) / RANGE_STEPS,
            on_value=lambda bounds: keep(tuple(bounds)),
        )
        return
    choices = sorted(column.dropna().unique().tolist())
    solara.SelectMultiple(
        name,
        values=list(selection.value.get(name, choices)),
        all_values=choices,
        on_value=keep,
    )


def _plots(browser: ExperimentBrowser, runs: pd.DataFrame, chosen: dict) -> None:
    """The output against the parameter, and the selected runs step by step."""
    parameter, output = chosen["parameter"].value, chosen["output"].value
    if runs.empty:
        solara.Warning("No run matches the filters.")
        return
    if parameter:
        summary = browser.against(parameter, output, runs)
        solara.FigureMatplotlib(
            against_figure(runs, summary, parameter, output), format="png"
        )
    shown = list(runs["run_id"])[:SERIES_RUNS]
    figure = series_figure(browser.series(output, shown), output)
    solara.FigureMatplotlib(figure, format="png")


def _controls(browser: ExperimentBrowser, selection, chosen: dict) -> None:
    """One filter per parameter, then the parameter and the output to plot."""
    every = browser.runs()
    for name in browser.parameters:
        _filter(name, every[name], selection)
    with solara.Row():
        solara.Select("parameter", values=browser.parameters, value=chosen["parameter"])
        solara.Select("output", values=browser.outputs, value=chosen["output"])


@solara.component
def ExperimentsTab(state: StudioState):
    """Browse a results store: filter its runs, plot an output against a parameter."""
    path = state.session.config.results
    browser, problem = solara.use_memo(
        lambda: open_store(path) if path else (None, None), [path]
    )
    selection = solara.use_reactive({})
    first = browser.parameters[0] if browser and browser.parameters else None
    chosen = {
        "parameter": solara.use_reactive(first),
        "output": solara.use_reactive(browser.outputs[0] if browser else None),
    }
    with solara.Card("Experiments"):
        if browser is None:
            solara.Markdown(problem or EXPERIMENTS_HELP)
            return
        solara.Text(browser.describe())
        _controls(browser, selection, chosen)
        runs = browser.select(selection.value)
        _plots(browser, runs, chosen)
        solara.DataFrame(runs)
        solara.FileDownload(
            lambda: runs.to_csv(index=False).encode("utf-8"),
            "selected-runs.csv",
            label="Selected runs (CSV)",
        )


def gather(state: StudioState) -> tuple[list[tuple[str, Any]], str | None]:
    """The results to show: the ``--analysis`` function's, then the session's own."""
    session = state.session
    found: list[tuple[str, Any]] = []
    problem = None
    if session.config.analysis:
        try:
            found = load_analyses(session.config.analysis)
        except Exception as error:  # the user's function may raise anything
            problem = (
                f"{session.config.analysis} raised {type(error).__name__}: {error}"
            )
    return found + list(session.analyses), problem


@solara.component
def AnalysisTab(state: StudioState):
    """Calibration posteriors (marginals, pairs, fits) and sensitivity results."""
    items, problem = solara.use_memo(lambda: gather(state), [])
    with solara.Card("Analysis"):
        if problem:
            solara.Error(problem)
        if not items:
            solara.Markdown(ANALYSIS_HELP)
        for name, result in items:
            try:
                view = view_of(name, result)
            except TypeError as error:
                solara.Warning(str(error))
                continue
            solara.Markdown(f"**{view.title}**")
            solara.FigureMatplotlib(view.figure(), format="png")
            solara.DataFrame(view.table)


__all__ = ["AnalysisTab", "ExperimentsTab"]
