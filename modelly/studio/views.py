"""The main area: the timeline scrubber, the space view, the plots and the agent table."""

from __future__ import annotations

import solara

from modelly.studio import data
from modelly.studio.i18n import t
from modelly.studio.scene import MATPLOTLIB_LIMIT, element_count
from modelly.studio.state import StudioState
from modelly.viz.mpl.figure import _SpaceFigure


def _scrub_buttons(state: StudioState, last: int) -> None:
    """Back to the live model; replay from the shown step."""
    session = state.session
    solara.Button(
        t("Back to live"),
        on_click=lambda: state.act(session.scrub, last),
        disabled=session.view is None,
        outlined=True,
    )
    solara.Button(
        t("Replay from here"),
        on_click=lambda: state.act(session.replay),
        disabled=session.view is None,
        outlined=True,
    )


def _scrub_slider(state: StudioState, span: tuple[int, int], shown: int) -> None:
    """The timeline's slider, from the first recorded step to the live one."""
    session = state.session
    first, last = span
    how = "replays the run" if session.replaying else "restores a checkpoint"
    with solara.Div(classes=["mx-timeline-track"]):
        solara.SliderInt(
            f"step (live: {last}); scrubbing {how}",
            value=shown,
            min=first,
            max=max(last, first + 1),
            on_value=lambda step: state.act(session.scrub, step),
            disabled=state.playing.value,
        )


@solara.component
def Scrubber(state: StudioState):
    """Move through the recorded run; replay from the shown step with changed values."""
    state.revision.get()
    session = state.session
    first, last = (int(bound) for bound in session.timeline.span)
    shown = int(session.shown.time)
    past = "is-past" if session.view is not None else ""
    with solara.Column(gap="0", classes=["mx-timeline-wrap"]):
        with solara.Row(classes=["mx-timeline", past], gap="0"):
            solara.Text(t("Timeline"), classes=["mx-timeline-title"])
            solara.Text(f"{shown} / {last}", classes=["mx-timeline-at"])
            _scrub_slider(state, (first, last), shown)
            _scrub_buttons(state, last)
        if session.view is not None:
            solara.Info(
                f"showing step {shown} of {last}: change parameters, then Replay from here",
                dense=True,
                classes=["mx-timeline-note"],
            )


@solara.component
def SpaceView(state: StudioState):
    """The model's space, drawn with the shared Matplotlib portrayal."""
    state.revision.get()
    session = state.session
    # One figure per session: the space's structure is drawn once, the agents per tick.
    live = solara.use_memo(_SpaceFigure, [])
    with solara.Card(t("Space")):
        if not live.can_draw(session.shown):
            solara.Text(t("This model has no grid or space Modelly can draw."))
            return
        count = element_count(session.shown)
        if count > MATPLOTLIB_LIMIT:
            solara.Text(
                f"{count} agents and edges: too many to redraw with Matplotlib at every "
                "step. The Map tab draws them with WebGL."
            )
            return
        with session.lock:
            figure = live.draw(session.shown, session.portrayal)
        solara.FigureMatplotlib(
            figure, format="png", dependencies=[state.revision.value]
        )


@solara.component
def SeriesView(state: StudioState):
    """The DataCollector's numeric model reporters over the run."""
    state.revision.get()
    session = state.session
    with solara.Card(t("Model reporters")):
        with session.lock:
            figure = data.series_figure(session.shown)
        if figure is None:
            solara.Text(
                t("No numeric model reporters: give the model a DataCollector.")
            )
            return
        solara.FigureMatplotlib(
            figure, format="png", dependencies=[state.revision.value]
        )


@solara.component
def AgentTable(state: StudioState):
    """The first agents, by unique_id, one column per attribute; filter by class."""
    state.revision.get()
    session = state.session
    chosen = solara.use_reactive(data.ALL_CLASSES)
    with session.lock:
        classes = data.agent_classes(session.shown)
        if chosen.value not in classes:
            chosen.value = data.ALL_CLASSES
        table = data.agent_table(session.shown, chosen.value, session.config.table_rows)
    with solara.Card(f"Agents (first {session.config.table_rows})"):
        solara.Select(t("class"), values=classes, value=chosen)
        if table.empty:
            solara.Text(t("No agents."))
            return
        solara.DataFrame(
            table, items_per_page=session.config.table_rows, scrollable=True
        )
