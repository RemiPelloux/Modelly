"""The Ensemble and Assimilation tabs: bands across replicates, and filters on observations."""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

import pandas as pd
import solara

from modelly.stream.particle import DEFAULT_THRESHOLD
from modelly.studio.assimilation import (
    DEFAULT_SD,
    DEFAULT_SPREAD,
    METHODS,
    PARTICLE,
    Assimilation,
    FilterSettings,
    adjustable,
    assimilate,
    read_observations,
)
from modelly.studio.ensembles import (
    DEFAULT_ENSEMBLE_STEPS,
    DEFAULT_REPLICATES,
    session_bands,
)
from modelly.studio.figures import (
    band_figure,
    ess_figure,
    trajectory_figure,
    weights_figure,
)
from modelly.studio.state import StudioState

FRACTION = {"min": 0.05, "max": 1.0, "step": 0.05}
ENSEMBLE_HELP = (
    "Runs new replicates of the parameter panel's values, each with a seed spawned from "
    "the panel's seed, and draws the mean, the median and the 5 to 95 % band of every "
    "numeric model reporter across them, step by step."
)
ASSIMILATION_HELP = (
    "Start Studio with `--observations observations.csv` (a `time` column and one column "
    "per observed model reporter) to assimilate them with a particle filter or an "
    "ensemble Kalman filter."
)


def attempt(state: StudioState, call: Callable[[], Any], error) -> Any:
    """``call()``; on an exception, log it, show it in ``error`` and return None."""
    try:
        found = call()
    except Exception as failure:  # a model error is shown, not raised into the UI
        message = f"{type(failure).__name__}: {failure}"
        state.session.say(f"error: {message}")
        state.session.say(traceback.format_exc(limit=-1).strip())
        error.set(message)
        return None
    error.set(None)
    return found


def _csv(frame: pd.DataFrame) -> Callable[[], bytes]:
    """A download callback for ``frame`` as CSV."""
    return lambda: frame.to_csv(index=False).encode("utf-8")


def _figure(figure) -> None:
    """Show a Matplotlib figure, or nothing for None."""
    if figure is not None:
        solara.FigureMatplotlib(figure, format="png")


@solara.component
def EnsembleTab(state: StudioState):
    """Replicates of the panel's values and their bands over time."""
    session = state.session
    replicates = solara.use_reactive(DEFAULT_REPLICATES)
    steps = solara.use_reactive(DEFAULT_ENSEMBLE_STEPS)
    bands = solara.use_reactive(None)
    error = solara.use_reactive(None)

    def run() -> None:
        found = attempt(
            state, lambda: session_bands(session, replicates.value, steps.value), error
        )
        bands.set(found)

    with solara.Card("Ensemble"):
        solara.Markdown(ENSEMBLE_HELP)
        with solara.Row():
            solara.InputInt("replicates", value=replicates)
            solara.InputInt("ensemble steps", value=steps)
            solara.Button("Run ensemble", on_click=run)
        if error.value:
            solara.Error(error.value)
        if bands.value is not None:
            _figure(band_figure(bands.value))
            solara.FileDownload(
                _csv(bands.value), "ensemble-bands.csv", label="Bands (CSV)"
            )


def _settings_inputs(session, values: dict) -> None:
    """The filter's inputs: method, replicates, error, threshold or parameters."""
    solara.Select("method", values=list(METHODS), value=values["method"])
    with solara.Row():
        solara.InputInt("replicates", value=values["replicates"])
        solara.InputFloat("observation sd", value=values["sd"])
    if values["method"].value == PARTICLE:
        solara.SliderFloat(
            "resample below this share of the ensemble",
            value=values["threshold"],
            **FRACTION,
        )
        return
    solara.SelectMultiple(
        "parameters to adjust",
        values=values["parameters"],
        all_values=adjustable(session),
    )
    solara.SliderFloat("starting spread", value=values["spread"], **FRACTION)


def _settings(values: dict) -> FilterSettings:
    """The ``FilterSettings`` the inputs hold."""
    return FilterSettings(
        method=values["method"].value,
        replicates=values["replicates"].value or DEFAULT_REPLICATES,
        sd=values["sd"].value or DEFAULT_SD,
        threshold=values["threshold"].value,
        parameters=tuple(values["parameters"].value),
        spread=values["spread"].value,
    )


def dashboard(result: Assimilation, settings: FilterSettings) -> None:
    """The filtered bands with the observations, then the filter's own diagnostics."""
    _figure(band_figure(result.bands, result.observations))
    if result.method == PARTICLE:
        solara.Markdown("**Effective sample size** (dots: resampled)")
        _figure(ess_figure(result.history, settings.replicates, settings.threshold))
        solara.Markdown("**Weights** before resampling")
        _figure(weights_figure(result.weights))
    else:
        solara.Markdown("**Parameters** adjusted: ensemble mean and one sd")
        _figure(trajectory_figure(result.history, settings.parameters))
    solara.DataFrame(result.history)
    with solara.Row():
        solara.FileDownload(_csv(result.bands), "filter-bands.csv", label="Bands (CSV)")
        solara.FileDownload(
            _csv(result.history), "filter-history.csv", label="History (CSV)"
        )


def use_filter_inputs() -> dict:
    """The filter inputs' reactive values, at their defaults (a hook: call it once)."""
    return {
        "method": solara.use_reactive(PARTICLE),
        "replicates": solara.use_reactive(DEFAULT_REPLICATES),
        "sd": solara.use_reactive(DEFAULT_SD),
        "threshold": solara.use_reactive(DEFAULT_THRESHOLD),
        "parameters": solara.use_reactive([]),
        "spread": solara.use_reactive(DEFAULT_SPREAD),
    }


def _runner(state: StudioState, observations, values: dict, shown: tuple):
    """The Assimilate button's callback; ``shown`` is the outcome and error to set."""
    outcome, error = shown

    def run() -> None:
        settings = _settings(values)
        found = attempt(
            state, lambda: assimilate(state.session, observations, settings), error
        )
        outcome.set(None if found is None else (found, settings))

    return run


@solara.component
def AssimilationTab(state: StudioState):
    """A particle filter or an ensemble Kalman filter over the observations file."""
    session = state.session
    path = session.config.observations
    observations = solara.use_memo(
        lambda: read_observations(path) if path else [], [path]
    )
    values = use_filter_inputs()
    outcome = solara.use_reactive(None)
    error = solara.use_reactive(None)
    with solara.Card("Assimilation"):
        if not path:
            solara.Markdown(ASSIMILATION_HELP)
            return
        solara.Text(f"{len(observations)} observation(s) from {path}")
        _settings_inputs(session, values)
        run = _runner(state, observations, values, (outcome, error))
        solara.Button("Assimilate", on_click=run)
        if error.value:
            solara.Error(error.value)
        if outcome.value is not None:
            dashboard(*outcome.value)


__all__ = ["AssimilationTab", "EnsembleTab"]
