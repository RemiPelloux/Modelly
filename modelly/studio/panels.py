"""The sidebar: the parameter panel, the run controls and the exports."""

from __future__ import annotations

import time
from functools import partial

import solara

from modelly.studio import data, exports
from modelly.studio.params import (
    BOOL,
    CHOICE,
    FLOAT,
    FRACTION,
    FRACTION_STEP,
    INT,
    TEXT,
    Parameter,
)
from modelly.studio.state import StudioState
from modelly.studio.timeline import CHECKPOINT_ERRORS

MS_PER_SECOND = 1000
DEFAULT_RUN_STEPS = 10
DRAW_TIMEOUT_S = 10
INTERVAL_RANGE = {"min": 0, "max": 1000, "step": 10}


def _parameter_widget(param: Parameter, value, on_value) -> None:
    """The input for one parameter, by kind."""
    if param.kind == BOOL:
        solara.Checkbox(label=param.name, value=value, on_value=on_value)
    elif param.kind == CHOICE:
        solara.Select(
            param.name, values=list(param.choices), value=value, on_value=on_value
        )
    elif param.kind == FRACTION:
        solara.SliderFloat(
            f"{param.name} = {value:.2f}",
            value=value,
            min=0.0,
            max=1.0,
            step=FRACTION_STEP,
            on_value=on_value,
        )
    elif param.kind == INT:
        solara.InputInt(param.name, value=value, on_value=on_value)
    elif param.kind == FLOAT:
        solara.InputFloat(param.name, value=value, on_value=on_value)
    elif param.kind == TEXT:
        solara.InputText(param.name, value=value, on_value=on_value)
    else:
        solara.Text(f"{param.name} = {param.default!r} (fixed)")


def _on_change(state: StudioState, restart, name: str | None):
    """Store a new value of parameter ``name`` (the seed when None); restart if asked."""
    session = state.session

    def on_value(value) -> None:
        if value is None:  # a cleared number field
            return
        if name is None:
            session.seed = value
        else:
            session.values[name] = value
        if restart.value:
            state.act(session.reset)

    return on_value


@solara.component
def ParameterPanel(state: StudioState):
    """One input per Scenario field, the seed, and whether a change restarts the run."""
    state.revision.get()
    session = state.session
    restart = solara.use_reactive(True)
    with solara.Card("Parameters"):
        for param in session.parameters:
            value = session.values.get(param.name, param.default)
            _parameter_widget(param, value, _on_change(state, restart, param.name))
        solara.InputInt(
            "seed", value=session.seed, on_value=_on_change(state, restart, None)
        )
        solara.Checkbox(label="Restart the run when a value changes", value=restart)


def _play(state: StudioState) -> None:
    """Step while playing, one step per interval, each once the last one is drawn."""
    while state.playing.value:
        state.drawn.clear()
        if not state.act(state.session.step, 1) or not state.session.model.running:
            state.playing.value = False
            return
        # Wait for the views to draw this step: stepping faster than they draw
        # would only queue renders.
        state.drawn.wait(DRAW_TIMEOUT_S)
        time.sleep(state.interval_ms.value / MS_PER_SECOND)


def _buttons(state: StudioState, steps) -> None:
    """Step, play or pause, reset; run N steps."""
    session, playing = state.session, state.playing.value
    idle = not playing and session.model.running
    with solara.Row():
        solara.Button(
            "Step", on_click=lambda: state.act(session.step, 1), disabled=not idle
        )
        solara.Button(
            "Pause" if playing else "Play",
            on_click=lambda: state.playing.set(not playing),
            disabled=not (playing or idle),
        )
        solara.Button(
            "Reset", on_click=lambda: state.act(session.reset), disabled=playing
        )
    with solara.Row():
        solara.InputInt("steps", value=steps)
        solara.Button(
            f"Run {steps.value}",
            on_click=lambda: state.act(session.step, steps.value or 0),
            disabled=not idle,
        )


@solara.component
def RunControls(state: StudioState):
    """Step, run N steps, play and pause, reset."""
    state.revision.get()
    model = state.session.model
    steps = solara.use_reactive(DEFAULT_RUN_STEPS)
    solara.lab.use_task(
        lambda: _play(state), dependencies=[state.playing.value], prefer_threaded=True
    )
    with solara.Card("Run"):
        stopped = "" if model.running else " (stopped)"
        solara.Text(f"step {model.time:g}{stopped}")
        _buttons(state, steps)
        solara.SliderInt(
            "pause between steps (ms)", value=state.interval_ms, **INTERVAL_RANGE
        )
        if state.error.value:
            solara.Error(state.error.value)


def _checkpoint(state: StudioState) -> bytes:
    """The shown model as a checkpoint, or an empty file with the reason logged."""
    try:
        return data.checkpoint_file(state.session.shown)
    except CHECKPOINT_ERRORS as error:
        state.session.say(f"checkpoint export failed: {error}".splitlines()[0])
        return b""


def _bundle(state: StudioState) -> bytes:
    """The live run as a ``modelly bundle`` zip, or an empty file with the reason logged."""
    try:
        return exports.bundle_bytes(state.session)
    except (ValueError, OSError) as error:  # a replayed run, or a model that won't load
        state.session.say(f"bundle export failed: {error}".splitlines()[0])
        return b""


def _reproducible(state: StudioState) -> list[tuple]:
    """The live run's session script and bundle."""
    session = state.session
    live = session.model
    stamp = f"{type(live).__name__.lower()}-step{live.time:g}"
    script = partial(exports.session_script, session)
    return [
        (script, exports.script_name(session), "Session script (live run, .py)"),
        (partial(_bundle, state), f"{stamp}-bundle.zip", "Bundle (live run, zip)"),
    ]


def _locked(session, make):
    """``make`` run under the session lock; an empty file when it gives None."""

    def run() -> bytes:
        with session.lock:
            return make() or b""

    return run


def _figures(state: StudioState, stamp: str) -> list[tuple]:
    """The space view and the reporters plot, in every figure format."""
    session = state.session
    found = []
    for fmt in data.FIGURE_FORMATS:
        kind = fmt.upper()
        space = partial(data.space_image, session, fmt)
        series = partial(data.series_image, session.shown, fmt)
        found.append((space, f"{stamp}-space.{fmt}", f"Space view ({kind})"))
        found.append((series, f"{stamp}-reporters.{fmt}", f"Reporters plot ({kind})"))
    return found


def downloads(state: StudioState) -> list[tuple]:
    """``(make the bytes, file name, label)`` for every export of the shown state."""
    session = state.session
    shown = session.shown
    name = type(shown).__name__.lower()
    stamp = f"{name}-step{shown.time:g}"
    formats = ["csv", "parquet"] if data.parquet_available() else ["csv"]
    tables = [
        (partial(data.data_bytes, shown, fmt), f"{stamp}-data.{fmt}", f"Data ({fmt})")
        for fmt in formats
    ]
    checkpoint = (
        partial(_checkpoint, state),
        f"{stamp}.ckpt",
        "Checkpoint of this state",
    )
    animation = (partial(data.animation_bytes, session), f"{name}-run.gif", "Run (GIF)")
    return [
        *_figures(state, stamp),
        *tables,
        checkpoint,
        animation,
        *_reproducible(state),
    ]


@solara.component
def ExportPanel(state: StudioState):
    """Download the figures, the collected data, a checkpoint and an animation."""
    state.revision.get()
    with solara.Card("Export"):
        for make, filename, label in downloads(state):
            solara.FileDownload(_locked(state.session, make), filename, label=label)
