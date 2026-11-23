"""The workbench's browser side: shortcuts, and the panel and tab the browser restores."""

import threading

import pytest

solara = pytest.importorskip("solara")
v = pytest.importorskip("ipyvuetify")

from modelly.studio import app  # noqa: E402
from modelly.studio.config import StudioConfig  # noqa: E402
from modelly.studio.state import StudioState  # noqa: E402
from modelly.studio.workbench import WorkbenchWidget, press  # noqa: E402
from tests.studio.test_studio_app import render  # noqa: E402

BOLTZMANN = "modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"
RUN = 5


def state() -> StudioState:
    """A Boltzmann session run ``RUN`` steps, with its state outside any page."""
    session = app.new_session(StudioConfig(target=BOLTZMANN))
    session.step(RUN)
    return StudioState(
        session=session,
        revision=solara.reactive(0),
        playing=solara.reactive(False),
        error=solara.reactive(None),
        interval_ms=solara.reactive(0),
        drawn=threading.Event(),
    )


def test_the_arrows_move_through_the_timeline_then_step():
    """Back scrubs, forward scrubs back towards live, then takes a new step."""
    studio = state()
    session = studio.session
    press(studio, "back")
    assert session.view is not None
    assert session.shown.time == RUN - 1
    press(studio, "forward")
    assert session.view is None  # the live step again
    press(studio, "forward")
    assert session.model.time == RUN + 1


def test_end_returns_to_live_and_back_stops_at_the_first_step():
    """End shows the live model; back from the first recorded step does nothing."""
    studio = state()
    session = studio.session
    first = session.timeline.span[0]
    for _ in range(RUN + 2):
        press(studio, "back")
    assert session.shown.time == first
    press(studio, "live")
    assert session.view is None


def test_space_plays_and_pauses_and_nothing_else_runs_while_playing():
    """Play toggles; while playing, the arrows are ignored, as the buttons are disabled."""
    studio = state()
    press(studio, "play")
    assert studio.playing.value
    press(studio, "forward")
    press(studio, "back")
    assert studio.session.view is None
    assert studio.session.model.time == RUN
    press(studio, "play")
    assert not studio.playing.value


def test_the_browser_restores_the_panel_and_the_tab():
    """What the template reads from local storage opens that panel and tab."""
    session = app.new_session(StudioConfig(target=BOLTZMANN))
    rc = render(session)
    widget = rc.find(WorkbenchWidget).widget
    widget.panel = "Export"
    widget.tab = "Agents"
    pressed = [
        b.attributes["aria-label"]
        for b in rc.find(v.Btn).widgets
        if "is-active" in str(b.class_)
    ]
    assert pressed == ["Export"]
    titles = " ".join(str(t.children) for t in rc.find(v.CardTitle).widgets)
    assert "Agents" in titles
    widget.tab = "No such tab"  # kept by another mode or an older Studio
    assert rc.find(v.Tabs).widget.v_model == 0


def test_a_shortcut_from_the_browser_reaches_the_session():
    """The template's key event steps the rendered session."""
    session = app.new_session(StudioConfig(target=BOLTZMANN))
    rc = render(session)
    rc.find(WorkbenchWidget).widget.vue_key("forward")
    assert session.model.time == 1
