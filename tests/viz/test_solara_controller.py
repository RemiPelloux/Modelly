"""Tests for the SolaraViz model controller: step, play/pause, reset and its loops."""

import threading

import ipyvuetify as vw
import pytest
import solara

import modelly
from modelly.space import OrthogonalMooreGrid
from modelly.viz.render.renderer import SpaceRenderer
from modelly.viz.solara.controller import (
    ModelController,
    _advance,
    _ControllerState,
    _play_loop,
    _render_buttons,
    _reset,
    _RunSettings,
    _use_controller_state,
    _visualization_loop,
    copy_renderer,
)
from modelly.viz.utils import update_counter


class CountingModel(modelly.Model):
    """Counts its steps and stops running after ``limit`` of them."""

    def __init__(self, limit=100, rng=None, scenario=None):
        """Create the instance."""
        super().__init__(rng=rng)
        self.limit = limit
        self.count = 0

    def step(self):
        """Step."""
        self.count += 1
        if self.count >= self.limit:
            self.running = False


def make_ctl(model, *, playing=False, render_interval=1, use_threads=False):
    """Make ctl."""
    settings = _RunSettings(
        solara.reactive(0),
        solara.reactive(render_interval),
        solara.reactive(use_threads),
    )
    return _ControllerState(
        model=solara.reactive(model),
        renderer=None,
        settings=settings,
        playing=solara.reactive(playing),
        running=solara.reactive(True),
        model_parameters=solara.reactive({"limit": 5}),
        pause_event=threading.Event(),
        error_message=solara.reactive(None),
    )


def test_advance_paused_steps_render_interval_times():
    """Advance paused steps render interval times."""
    ctl = make_ctl(CountingModel(), render_interval=3)
    before = update_counter.value
    _advance(ctl)
    assert ctl.model.value.count == 3
    assert ctl.running.value is True
    assert update_counter.value == before + 1


def test_advance_paused_records_model_stop():
    """Advance paused records model stop."""
    ctl = make_ctl(CountingModel(limit=2), render_interval=2)
    _advance(ctl)
    assert ctl.running.value is False


def test_advance_playing_without_threads_updates_views():
    """Advance playing without threads updates views."""
    ctl = make_ctl(CountingModel(), playing=True, render_interval=4)
    before = update_counter.value
    _advance(ctl)
    assert ctl.model.value.count == 4
    assert update_counter.value == before + 1


def test_advance_playing_with_threads_leaves_update_to_render_thread():
    """Advance playing with threads leaves update to render thread."""
    ctl = make_ctl(CountingModel(), playing=True, render_interval=2, use_threads=True)
    before = update_counter.value
    _advance(ctl)
    assert ctl.model.value.count == 2
    assert update_counter.value == before


def test_advance_playing_stops_when_paused_mid_interval():
    """Advance playing stops when paused mid interval."""
    model = CountingModel()
    ctl = make_ctl(model, playing=True, render_interval=10)
    original_step = model.step

    def step_then_pause():
        original_step()
        ctl.playing.value = False

    model.step = step_then_pause
    _advance(ctl)
    assert model.count == 1


def test_reset_recreates_model_from_parameters():
    """Reset recreates model from parameters."""
    old = CountingModel(limit=100)
    old.count = 9
    ctl = make_ctl(old, playing=True)
    ctl.running.value = False
    ctl.error_message.value = "old error"
    ctl.pause_event.set()
    _reset(ctl)
    new = ctl.model.value
    assert new is not old
    assert isinstance(new, CountingModel)
    assert new.limit == 5
    assert new.count == 0
    assert ctl.playing.value is False
    assert ctl.running.value is True
    assert ctl.error_message.value is None
    assert not ctl.pause_event.is_set()


class GridModel(CountingModel):
    """Test helper GridModel."""

    def __init__(self, limit=100, rng=None, scenario=None):
        """Create the instance."""
        super().__init__(limit=limit, rng=rng)
        self.grid = OrthogonalMooreGrid((3, 3), random=self.random)


def test_reset_copies_the_renderer_onto_the_new_model():
    """Reset copies the renderer onto the new model."""
    model = GridModel()
    renderer = SpaceRenderer(model, backend="matplotlib")
    portrayal = lambda agent: {}  # noqa: E731
    renderer.agent_portrayal = portrayal
    ctl = make_ctl(model)
    ctl.renderer = solara.reactive(renderer)
    _reset(ctl)
    new_renderer = ctl.renderer.value
    assert new_renderer is not renderer
    assert new_renderer.space is ctl.model.value.grid
    assert new_renderer.agent_portrayal is portrayal
    assert new_renderer.backend == "matplotlib"


def test_copy_renderer_skips_unset_attributes():
    """Copy renderer skips unset attributes."""
    model = GridModel()
    renderer = SpaceRenderer(model, backend="altair")
    renderer.space_kwargs = {"color": "red"}
    other = GridModel()
    copy = copy_renderer(renderer, other)
    assert type(copy) is SpaceRenderer
    assert copy.space is other.grid
    assert copy.backend == "altair"
    assert copy.space_kwargs == {"color": "red"}
    assert copy.agent_mesh is None


def test_play_loop_steps_until_paused_and_signals_render_thread():
    """Play loop steps until paused and signals render thread."""
    ctl = make_ctl(CountingModel(), playing=True, use_threads=True)
    calls = []

    def do_step():
        calls.append(1)
        if len(calls) == 3:
            ctl.playing.value = False

    _play_loop(ctl, do_step)
    assert len(calls) == 3
    assert ctl.pause_event.is_set()


def test_play_loop_stops_when_model_stops_running():
    """Play loop stops when model stops running."""
    ctl = make_ctl(CountingModel(), playing=True)

    def do_step():
        ctl.running.value = False

    _play_loop(ctl, do_step)
    assert not ctl.pause_event.is_set()


def test_play_loop_reports_step_errors(capsys):
    """Play loop reports step errors."""
    ctl = make_ctl(CountingModel(), playing=True)

    def do_step():
        raise RuntimeError("kaput")

    _play_loop(ctl, do_step)
    assert ctl.error_message.value == "error in step: kaput"
    assert "RuntimeError" in capsys.readouterr().err


class _OneShotEvent:
    """Pause event whose wait ends the loop after ``rounds`` signals."""

    def __init__(self, ctl, rounds=2, error=None):
        self.ctl, self.rounds, self.error = ctl, rounds, error
        self.cleared = 0

    def wait(self):
        if self.error is not None:
            raise self.error
        self.rounds -= 1
        if self.rounds == 0:
            self.ctl.playing.value = False

    def clear(self):
        self.cleared += 1


def test_visualization_loop_refreshes_on_each_signal():
    """Visualization loop refreshes on each signal."""
    ctl = make_ctl(CountingModel(), playing=True, use_threads=True)
    ctl.pause_event = _OneShotEvent(ctl, rounds=2)
    before = update_counter.value
    _visualization_loop(ctl)
    assert ctl.pause_event.cleared == 2
    assert update_counter.value == before + 2


def test_visualization_loop_is_idle_without_threads():
    """Visualization loop is idle without threads."""
    ctl = make_ctl(CountingModel(), playing=True, use_threads=False)
    ctl.pause_event = _OneShotEvent(ctl, error=AssertionError("must not wait"))
    _visualization_loop(ctl)
    assert ctl.error_message.value is None


def test_visualization_loop_reports_errors(capsys):
    """Visualization loop reports errors."""
    ctl = make_ctl(CountingModel(), playing=True, use_threads=True)
    ctl.pause_event = _OneShotEvent(ctl, error=RuntimeError("no screen"))
    _visualization_loop(ctl)
    assert ctl.error_message.value == "error in visualization: no screen"
    assert "RuntimeError" in capsys.readouterr().err


def _settings(play_interval=0, render_interval=1):
    # The controller reads ``.value`` from these, so pass reactives as SolaraViz does.
    return {
        "play_interval": solara.reactive(play_interval),
        "render_interval": solara.reactive(render_interval),
        "use_threads": solara.reactive(False),
    }


def _button(rc, label):
    return rc.find(vw.Btn, children=[label]).widget


def test_model_controller_step_and_reset_buttons():
    """Model controller step and reset buttons."""
    model = solara.reactive(CountingModel(limit=100))
    first = model.value
    _, rc = solara.render(
        ModelController(
            model, model_parameters={"limit": 7}, **_settings(render_interval=2)
        ),
        handle_error=False,
    )
    _button(rc, "Step").click()
    assert first.count == 2
    _button(rc, "Reset").click()
    assert model.value is not first
    assert model.value.limit == 7
    assert model.value.count == 0


def test_model_controller_disables_buttons_when_model_stopped():
    """Model controller disables buttons when model stopped."""
    model = solara.reactive(CountingModel(limit=1))
    _, rc = solara.render(ModelController(model, **_settings()), handle_error=False)
    step = _button(rc, "Step")
    assert not step.disabled
    step.click()
    rc.render(ModelController(model, **_settings()))
    assert _button(rc, "Step").disabled
    assert _button(rc, "▶").disabled


def test_model_controller_default_parameters_reset_to_defaults():
    """Model controller default parameters reset to defaults."""
    model = solara.reactive(CountingModel(limit=3))
    _, rc = solara.render(ModelController(model, **_settings()), handle_error=False)
    _button(rc, "Reset").click()
    assert model.value.limit == 100


def test_model_controller_play_pause_toggles_label():
    """Model controller play pause toggles label."""
    model = solara.reactive(CountingModel(limit=1))
    _, rc = solara.render(ModelController(model, **_settings()), handle_error=False)
    _button(rc, "▶").click()
    pause = _button(rc, "❚❚")
    assert _button(rc, "Step").disabled
    pause.click()
    assert _button(rc, "▶") is not None


@pytest.mark.parametrize("message", [None, "something broke"])
def test_render_buttons_shows_error_message(message):
    """Render buttons shows error message."""

    @solara.component
    def Buttons():
        settings = _RunSettings(0, 1, False)
        ctl = _use_controller_state(
            solara.reactive(CountingModel()), None, None, settings
        )
        assert ctl.model_parameters.value == {}
        ctl.error_message.value = message
        _render_buttons(ctl, lambda: None, lambda: None, lambda: None)

    _, rc = solara.render(Buttons(), handle_error=False)
    alerts = rc.find(vw.Alert)
    if message is None:
        alerts.assert_empty()
    else:
        assert message in str(alerts.widget.children)
