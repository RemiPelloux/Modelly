"""Model execution controls for SolaraViz: step, play/pause and reset."""

from __future__ import annotations

import logging
import threading
import time
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NamedTuple

import solara
import solara.lab

from modelly.log import create_module_logger, function_logger
from modelly.viz.render.renderer import SpaceRenderer
from modelly.viz.solara.model_kwargs import _build_model_init_kwargs
from modelly.viz.utils import force_update

if TYPE_CHECKING:
    from modelly.core.model import Model

_modelly_logger = create_module_logger()

_MS_PER_SECOND = 1000
_RENDERER_ATTRIBUTES = (
    "agent_portrayal",
    "property_layer_portrayal",
    "draw_space_kwargs",
    "draw_agent_kwargs",
    # Legacy names, kept so renderers that set them still have them copied.
    "space_kwargs",
    "agent_kwargs",
    "space_mesh",
    "agent_mesh",
    "property_layer_mesh",
    "post_process_func",
)


class _RunSettings(NamedTuple):
    """Playback settings shared by the sidebar sliders and the controller."""

    play_interval: Any
    render_interval: Any
    use_threads: Any


@dataclass
class _ControllerState:
    """Reactive state the controller callbacks act on."""

    model: Any
    renderer: Any
    settings: _RunSettings
    playing: Any
    running: Any
    model_parameters: Any
    pause_event: threading.Event
    error_message: Any


def _use_controller_state(model, renderer, model_parameters, settings):
    """Run the controller's hooks, always in the same order, and bundle their state."""
    playing = solara.use_reactive(False)
    running = solara.use_reactive(True)

    if model_parameters is None:
        model_parameters = {}
    model_parameters = solara.use_reactive(model_parameters)
    pause_event = solara.use_memo(threading.Event, [])

    error_message = solara.use_reactive(None)
    return _ControllerState(
        model=model,
        renderer=renderer,
        settings=settings,
        playing=playing,
        running=running,
        model_parameters=model_parameters,
        pause_event=pause_event,
        error_message=error_message,
    )


def _play_loop(ctl: _ControllerState, do_step) -> None:
    """Step the model while playing, signalling the render thread when threaded."""
    try:
        while ctl.running.value and ctl.playing.value:
            time.sleep(ctl.settings.play_interval.value / _MS_PER_SECOND)
            do_step()
            if ctl.settings.use_threads.value:
                ctl.pause_event.set()
    except Exception as e:
        ctl.error_message.value = f"error in step: {e}"
        traceback.print_exc()
        return


def _visualization_loop(ctl: _ControllerState) -> None:
    """Refresh the views each time the play loop signals, when running threaded."""
    if ctl.settings.use_threads.value:
        try:
            while ctl.playing.value and ctl.running.value:
                ctl.pause_event.wait()
                ctl.pause_event.clear()
                force_update()

        except Exception as e:
            ctl.error_message.value = f"error in visualization: {e}"
            traceback.print_exc()


def _advance(ctl: _ControllerState) -> None:
    """Advance the model by ``render_interval`` steps and refresh the views."""
    model = ctl.model
    if ctl.playing.value:
        for _ in range(ctl.settings.render_interval.value):
            model.value.step()
            ctl.running.value = model.value.running
            if not ctl.playing.value:
                break
        if not ctl.settings.use_threads.value:
            force_update()

    else:
        for _ in range(ctl.settings.render_interval.value):
            model.value.step()
            ctl.running.value = model.value.running
        force_update()


def _reset(ctl: _ControllerState) -> None:
    """Re-instantiate the model (and its renderer) from the current parameters."""
    model = ctl.model
    ctl.error_message.set(None)
    ctl.playing.value = False
    ctl.running.value = True
    ctl.pause_event.clear()
    _modelly_logger.log(
        logging.DEBUG,
        f"creating new {type(model.value)} instance with {ctl.model_parameters.value}",
    )
    kwargs = _build_model_init_kwargs(
        model.value,
        ctl.model_parameters.value,
        add_scenario_when_empty=True,
        require_model_accepts_scenario=True,
    )

    model.value = type(model.value)(**kwargs)
    if ctl.renderer is not None:
        ctl.renderer.value = copy_renderer(ctl.renderer.value, model.value)
        force_update()


def _make_handlers(ctl: _ControllerState):
    """Build the logged step, reset and play/pause button callbacks."""

    @function_logger(__name__)
    def do_step():
        """Advance the model by the number of steps specified by the render_interval slider."""
        _advance(ctl)

    @function_logger(__name__)
    def do_reset():
        """Reset the model to its initial state."""
        _reset(ctl)

    @function_logger(__name__)
    def do_play_pause():
        """Toggle play/pause."""
        ctl.playing.value = not ctl.playing.value

    return do_step, do_reset, do_play_pause


def _render_buttons(ctl: _ControllerState, do_reset, do_play_pause, do_step) -> None:
    """Render the reset, play/pause and step buttons and any error message."""
    playing, running = ctl.playing, ctl.running
    with solara.Row(justify="space-between"):
        solara.Button(label="Reset", color="primary", on_click=do_reset)
        solara.Button(
            label="▶" if not playing.value else "❚❚",
            color="primary",
            on_click=do_play_pause,
            disabled=not running.value,
        )
        solara.Button(
            label="Step",
            color="primary",
            on_click=do_step,
            disabled=playing.value or not running.value,
        )

    if ctl.error_message.value:
        solara.Error(label=ctl.error_message.value)


@solara.component
def ModelController(
    model: solara.Reactive[Model],
    *,
    renderer: solara.Reactive[SpaceRenderer] | None = None,
    model_parameters: dict | solara.Reactive[dict] = None,
    play_interval: int | solara.Reactive[int] = 100,
    render_interval: int | solara.Reactive[int] = 1,
    use_threads: bool | solara.Reactive[bool] = False,
):
    """Create controls for model execution (step, play, pause, reset).

    Args:
        model: Reactive model instance
        renderer: SpaceRenderer instance to render the model's space.
        model_parameters: Reactive parameters for (re-)instantiating a model.
        play_interval: Interval for playing the model steps in milliseconds.
        render_interval: Controls how often the plots are updated during simulation steps.Higher value reduce update frequency.
        use_threads: Flag for indicating whether to utilize multi-threading for model execution.
    """
    settings = _RunSettings(
        solara.use_reactive(play_interval),
        solara.use_reactive(render_interval),
        solara.use_reactive(use_threads),
    )
    ctl = _use_controller_state(model, renderer, model_parameters, settings)
    do_step, do_reset, do_play_pause = _make_handlers(ctl)

    def step():
        _play_loop(ctl, do_step)

    def visualization_task():
        _visualization_loop(ctl)

    solara.lab.use_task(
        step, dependencies=[ctl.playing.value, ctl.running.value], prefer_threaded=True
    )

    solara.use_thread(
        visualization_task,
        dependencies=[ctl.playing.value, ctl.running.value],
    )

    _render_buttons(ctl, do_reset, do_play_pause, do_step)


def copy_renderer(renderer: SpaceRenderer, model: Model):
    """Create a new renderer instance with the same configuration as the original."""
    new_renderer = type(renderer)(model=model, backend=renderer.backend)

    for attr in _RENDERER_ATTRIBUTES:
        if getattr(renderer, attr, None) is not None:
            value_to_copy = getattr(renderer, attr)
            setattr(new_renderer, attr, value_to_copy)

    return new_renderer
