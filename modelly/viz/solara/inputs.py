"""Model parameter inputs for SolaraViz: the ModelCreator and UserInputs components."""

from __future__ import annotations

import contextlib
import functools
from typing import TYPE_CHECKING

import solara

from modelly.log import function_logger
from modelly.viz.solara.model_kwargs import _check_model_params, split_model_params
from modelly.viz.solara.params import Slider

if TYPE_CHECKING:
    from modelly.core.model import Model


def _default_parameter_values(fixed_params, user_adjust_params):
    """Return the initial value of every fixed and user-adjustable parameter."""
    return {
        **fixed_params,
        **{k: v.get("value") for k, v in user_adjust_params.items()},
    }


@solara.component
def ModelCreator(
    model: solara.Reactive[Model],
    user_params: dict,
    *,
    model_parameters: dict | solara.Reactive[dict] = None,
):
    """Solara component for creating and managing a model instance with user-defined parameters.

    This component allows users to create a model instance with specified parameters and seed.
    It provides an interface for adjusting model parameters and reseeding the model's random
    number generator.

    Args:
        model: A reactive model instance. This is the main model to be created and managed.
        user_params: Parameters for (re-)instantiating a model. Can include user-adjustable parameters and fixed parameters. Defaults to None.
        model_parameters: reactive parameters for reinitializing the model

    Returns:
        solara.component: A Solara component that renders the model creation and management interface.

    Example:
        >>> model = solara.reactive(MyModel())
        >>> model_params = {
        >>>     "param1": {"type": "slider", "value": 10, "min": 0, "max": 100},
        >>>     "param2": {"type": "slider", "value": 5, "min": 1, "max": 10},
        >>> }
        >>> creator = ModelCreator(model, model_params)
        >>> creator

    Notes:
        - The `model_params` argument should be a dictionary where keys are parameter names and values either fixed values
          or are dictionaries containing parameter details such as type, value, min, and max.
        - The `seed` argument ensures reproducibility by setting the initial seed for the model's random number generator.
        - The component provides an interface for adjusting user-defined parameters and reseeding the model.
    """
    if model_parameters is None:
        model_parameters = {}
    model_parameters = solara.use_reactive(model_parameters)

    solara.use_effect(
        lambda: _check_model_params(model.value, user_params),
        [model.value],
    )
    user_adjust_params, fixed_params = split_model_params(user_params)

    # Use solara.use_effect to run the initialization code only once
    solara.use_effect(
        # set model_parameters to the default values for all parameters
        lambda: model_parameters.set(
            _default_parameter_values(fixed_params, user_adjust_params)
        ),
        [],
    )

    @function_logger(__name__)
    def on_change(name, value):
        model_parameters.value = {**model_parameters.value, name: value}

    UserInputs(user_adjust_params, on_change=on_change)


def _render_slider_param(options: Slider, change_handler) -> None:
    """Render a :class:`Slider` parameter as an int or float slider."""
    slider_class = solara.SliderFloat if options.is_float_slider else solara.SliderInt
    slider_class(
        options.label,
        value=options.value,
        on_value=change_handler,
        min=options.min,
        max=options.max,
        step=options.step,
    )


def _render_dict_slider(label, options, change_handler, *, slider_class) -> None:
    """Render a ``SliderInt`` or ``SliderFloat`` dict parameter."""
    slider_class(
        label,
        value=options.get("value"),
        on_value=change_handler,
        min=options.get("min"),
        max=options.get("max"),
        step=options.get("step"),
    )


def _render_select(label, options, change_handler) -> None:
    """Render a ``Select`` dict parameter."""
    solara.Select(
        label,
        value=options.get("value"),
        on_value=change_handler,
        values=options.get("values"),
    )


def _render_checkbox(label, options, change_handler) -> None:
    """Render a ``Checkbox`` dict parameter."""
    solara.Checkbox(
        label=label,
        on_value=change_handler,
        value=options.get("value"),
    )


def _render_input_text(label, options, change_handler) -> None:
    """Render an ``InputText`` dict parameter, converting input to int or float when possible."""

    def input_change_handler(value):
        converted = value
        with contextlib.suppress(ValueError, TypeError):
            converted = int(value)
            change_handler(converted)
            return
        with contextlib.suppress(ValueError, TypeError):
            converted = float(value)
        change_handler(converted)

    solara.InputText(
        label=label,
        on_value=input_change_handler,
        value=str(options.get("value")),
    )


_DICT_INPUT_RENDERERS = {
    "SliderInt": functools.partial(_render_dict_slider, slider_class=solara.SliderInt),
    "SliderFloat": functools.partial(
        _render_dict_slider, slider_class=solara.SliderFloat
    ),
    "Select": _render_select,
    "Checkbox": _render_checkbox,
    "InputText": _render_input_text,
}


def _render_user_input(name, options, on_change) -> None:
    """Render the input widget for one user-adjustable parameter."""

    def change_handler(value, name=name):
        on_change(name, value)

    if isinstance(options, Slider):
        _render_slider_param(options, change_handler)
        return

    # label for the input is "label" from options or name
    label = options.get("label", name)
    input_type = options.get("type")
    render = next(
        (fn for key, fn in _DICT_INPUT_RENDERERS.items() if input_type == key), None
    )
    if render is None:
        raise ValueError(f"{input_type} is not a supported input type")
    render(label, options, change_handler)


@solara.component
def UserInputs(user_params, on_change=None):
    """Initialize user inputs for configurable model parameters.

    Currently supports :class:`solara.SliderInt`, :class:`solara.SliderFloat`,
    :class:`solara.Select`, and :class:`solara.Checkbox`.

    Args:
        user_params: Dictionary with options for the input, including label, min and max values, and other fields specific to the input type.
        on_change: Function to be called with (name, value) when the value of an input changes.
    """
    for name, options in user_params.items():
        _render_user_input(name, options, on_change)
