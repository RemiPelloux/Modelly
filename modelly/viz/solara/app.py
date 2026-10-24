"""Modelly visualization module for creating interactive model visualizations.

This module provides components to create browser- and Jupyter notebook-based visualizations of
Modelly models, allowing users to watch models run step-by-step and interact with model parameters.

Key features:
    - SolaraViz: Main component for creating visualizations, supporting grid displays and plots
    - ModelController: Handles model execution controls (step, play, pause, reset)
    - UserInputs: Generates UI elements for adjusting model parameters

The module uses Solara for rendering in Jupyter notebooks or as standalone web applications.
It supports various types of visualizations including matplotlib plots, agent grids, and
custom visualization components.

Usage:
    1. Define an agent_portrayal function to specify how agents should be displayed
    2. Set up model_params to define adjustable parameters
    3. Create a SolaraViz instance with your model, parameters, and desired measures
    4. Display the visualization in a Jupyter notebook or run as a Solara app

See the Visualization Tutorial and example models for more details.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

import reacton.core
import solara
import solara.lab

import modelly.viz.altair.components as components_altair
from modelly.log import function_logger
from modelly.viz.console.console import CommandConsole
from modelly.viz.render.renderer import SpaceRenderer
from modelly.viz.solara.controller import ModelController, _RunSettings, copy_renderer
from modelly.viz.solara.inputs import ModelCreator, UserInputs
from modelly.viz.solara.layout import ComponentsView, make_initial_grid_layout
from modelly.viz.solara.model_kwargs import check_param_is_fixed, split_model_params
from modelly.viz.solara.params import Slider, UserParam
from modelly.viz.solara.space_view import (
    SpaceRendererComponent,
    create_space_component,
)
from modelly.viz.utils import update_counter

if TYPE_CHECKING:
    from modelly.core.model import Model

__all__ = [
    "ComponentsView",
    "JupyterViz",
    "ModelController",
    "ModelCreator",
    "ShowSteps",
    "Slider",
    "SolaraViz",
    "SpaceRendererComponent",
    "UserInputs",
    "UserParam",
    "check_param_is_fixed",
    "copy_renderer",
    "create_space_component",
    "make_initial_grid_layout",
    "split_model_params",
]

_SUPPORTED_MODEL_PARAM_TYPES = (UserParam, dict, int, float, bool, str)
_PLAY_INTERVAL_RANGE = {"min": 1, "max": 500, "step": 10}
_RENDER_INTERVAL_RANGE = {"min": 1, "max": 100, "step": 2}


def _validate_model_params(model_params: dict) -> None:
    for key, val in model_params.items():
        if not isinstance(val, _SUPPORTED_MODEL_PARAM_TYPES):
            raise TypeError(
                f"model_params['{key}'] has unsupported type '{type(val).__name__}'. "
                "Use Modelly's Slider wrapper or a primitive (int, float, bool, str) "
                "from modelly.viz instead of raw Solara components."
            )


def _check_model_is_instance(model) -> None:
    """Raise when a model class (rather than an instance) is passed to SolaraViz."""
    if isinstance(model, type):
        raise TypeError(
            f"SolaraViz requires an initialized model instance, not a model class. "
            f"Did you mean: SolaraViz({model.__name__}(), ...) instead of SolaraViz({model.__name__}, ...)?"
        )
    if isinstance(model, solara.Reactive) and isinstance(model.value, type):
        raise TypeError(
            f"SolaraViz requires an initialized model instance, not a model class. "
            f"Did you mean: SolaraViz({model.value.__name__}(), ...) instead of SolaraViz({model.value.__name__}, ...)?"
        )


def _resolve_components(components) -> list:
    """Expand ``"default"`` into the default Altair space component on page 0."""
    if components != "default":
        return components
    return [
        (
            components_altair.make_altair_space(
                agent_portrayal=None,
                property_layer_portrayal=None,
                post_process=None,
            ),
            0,
        )
    ]


def _render_app_bar(name: str | None, model) -> None:
    """Render the app bar with the visualization title and the theme toggle."""
    with solara.AppBar():
        solara.AppBarTitle(name if name else type(model).__name__)
        solara.lab.ThemeToggle()


def _render_interval_controls(settings: _RunSettings) -> None:
    """Render the play/render interval sliders and the threads checkbox."""
    play_interval, render_interval, use_threads = settings
    solara.SliderInt(
        label="Play Interval (ms)",
        value=play_interval,
        on_value=play_interval.set,
        **_PLAY_INTERVAL_RANGE,
    )
    solara.SliderInt(
        label="Render Interval (steps)",
        value=render_interval,
        on_value=render_interval.set,
        **_RENDER_INTERVAL_RANGE,
    )
    if use_threads.value:
        solara.Text("Increase play interval to avoid skipping plots")

    def set_reactive_use_threads(value):
        use_threads.set(value)

    solara.Checkbox(
        label="Use Threads", value=use_threads, on_value=set_reactive_use_threads
    )


def _render_controls(model, renderer, model_parameters, settings: _RunSettings):
    """Render the "Controls" card: playback settings and the model controller."""
    with solara.Card("Controls"):
        _render_interval_controls(settings)
        ModelController(
            model,
            renderer=renderer,
            model_parameters=model_parameters,
            play_interval=settings.play_interval,
            render_interval=settings.render_interval,
            use_threads=settings.use_threads,
        )


def _render_model_cards(model, model_params: dict, model_parameters) -> None:
    """Render the "Model Parameters" and "Information" cards."""
    with solara.Card("Model Parameters"):
        ModelCreator(model, model_params, model_parameters=model_parameters)
    with solara.Card("Information"):
        ShowSteps(model.value)


def _use_reactive_renderer(renderer):
    """Wrap a plain SpaceRenderer in a reactive variable (a hook, called on every render)."""
    if isinstance(renderer, SpaceRenderer):
        return solara.use_reactive(renderer)  # noqa: RUF100  # noqa: SH102
    return renderer


def _with_space_component(components, renderer) -> list:
    """Copy the components, prepending the renderer's space component on page 0."""
    # Make a copy of the components to avoid modifying the original list
    display_components = list(components)
    if renderer is not None:
        display_components.insert(0, (create_space_component(renderer.value), 0))
    return display_components


def _render_console(display_components: list, model, console_kwargs: dict) -> None:
    """Move the command console, when requested, from the pages into the sidebar."""
    if CommandConsole not in display_components:
        return
    display_components.remove(CommandConsole)
    additional_imports = console_kwargs.get("additional_imports", {})
    with solara.Card("Command Console"):
        CommandConsole(model, additional_imports=additional_imports)


@solara.component
@function_logger(__name__)
def SolaraViz(
    model: Model | solara.Reactive[Model],
    renderer: SpaceRenderer | None = None,
    components: list[tuple[reacton.core.Component], int]
    | list[tuple[Callable[[Model], reacton.core.Component], 0]]
    | Literal["default"] = [],  # noqa: B006
    *,
    play_interval: int = 100,
    render_interval: int = 1,
    model_params=None,
    name: str | None = None,
    use_threads: bool = False,
    **console_kwargs,
):
    """Solara visualization component.

    This component provides a visualization interface for a given model using Solara.
    It supports various visualization components and allows for interactive model
    stepping and parameter adjustments.

    Args:
        model (Model | solara.Reactive[Model]): A Model instance or a reactive Model.
            This is the main model to be visualized. If a non-reactive model is provided,
            it will be converted to a reactive model.
        renderer (SpaceRenderer): A SpaceRenderer instance to render the model's space.
        components (list[tuple[solara.component], int] | Literal["default"], optional): List of solara
            (components, page) or functions that return a solara (component, page).
            These components are used to render different parts of the model visualization.
            Defaults to "default", which uses the default Altair space visualization on page 0.
        play_interval (int, optional): Interval for playing the model steps in milliseconds.
            This controls the speed of the model's automatic stepping. Defaults to 100 ms.
        render_interval (int, optional): Controls how often plots are updated during a simulation,
            allowing users to skip intermediate steps and update graphs less frequently.
        use_threads: Flag for indicating whether to utilize multi-threading for model execution.
            When checked, the model will utilize multiple threads,adjust based on system capabilities.
        model_params (dict, optional): Parameters for (re-)instantiating a model.
            Can include user-adjustable parameters and fixed parameters. Defaults to None.
        name (str | None, optional): Name of the visualization. Defaults to the model's class name.
        **console_kwargs (dict, optional): Arguments to pass to the command console.
            Currently supported arguments:
            - additional_imports: Dictionary of names to objects to import into the command console.
                - Example:
                    >>> console_kwargs = {"additional_imports": {"numpy": np}}
                    >>> SolaraViz(model, console_kwargs=console_kwargs)

    Returns:
        solara.component: A Solara component that renders the visualization interface for the model.

    Example:
        >>> model = MyModel()
        >>> page = SolaraViz(model)
        >>> page

    Notes:
        - The `model` argument can be either a direct model instance or a reactive model. If a direct
          model instance is provided, it will be converted to a reactive model using `solara.use_reactive`.
        - The `play_interval` argument controls the speed of the model's automatic stepping. A lower
          value results in faster stepping, while a higher value results in slower stepping.
        - The `render_interval` argument determines how often plots are updated during simulation. Higher values
          reduce update frequency, resulting in faster execution.
    """
    components = _resolve_components(components)
    model_params = {} if model_params is None else model_params
    _validate_model_params(model_params)
    _check_model_is_instance(model)
    # Convert model to reactive
    if not isinstance(model, solara.Reactive):
        model = solara.use_reactive(model)  # noqa: RUF100  # noqa: SH102
    reactive_model_parameters = solara.use_reactive({})
    settings = _RunSettings(
        solara.use_reactive(play_interval),
        solara.use_reactive(render_interval),
        solara.use_reactive(use_threads),
    )
    renderer = _use_reactive_renderer(renderer)
    display_components = _with_space_component(components, renderer)

    _render_app_bar(name, model.value)
    with solara.Sidebar(), solara.Column():
        _render_controls(model, renderer, reactive_model_parameters, settings)
        _render_model_cards(model, model_params, reactive_model_parameters)
        _render_console(display_components, model.value, console_kwargs)
    # Render the main components view
    ComponentsView(display_components, model.value)


JupyterViz = SolaraViz


@solara.component
def ShowSteps(model):
    """Display the current step of the model."""
    update_counter.get()
    return solara.Text(f"Time: {model.time}")
