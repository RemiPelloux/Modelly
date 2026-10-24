"""Model parameter handling for SolaraViz: validation, splitting and re-instantiation kwargs."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from modelly.scenarios import Scenario
from modelly.viz.solara.params import Slider

if TYPE_CHECKING:
    from modelly.core.model import Model

_NON_KEYWORD_PARAM_KINDS = (
    inspect.Parameter.POSITIONAL_ONLY,
    inspect.Parameter.VAR_POSITIONAL,
)
_IMPLICIT_INIT_PARAMS = ["self", "kwargs", "args", "scenario"]
_ALWAYS_ACCEPTED_PARAMS = ["rng", "seed"]


def _get_scenario_defaults(scenario: Scenario) -> dict[str, Any]:
    """Return defaults for a scenario instance, validating scenario type."""
    scenario_class = type(scenario)
    if not issubclass(scenario_class, Scenario):
        raise ValueError(
            "Expected model.scenario to be a subclass instance of modelly.scenarios.Scenario."
        )

    defaults = getattr(scenario, "_scenario_defaults", {}).copy()
    defaults["rng"] = None

    return defaults


def _split_scenario_params(
    model_parameters: dict[str, Any],
    scenario_defaults: dict[str, Any],
    model_init_params,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split parameters into model kwargs and scenario kwargs."""
    kwargs: dict[str, Any] = {}
    scenario_kwargs: dict[str, Any] = {}
    for key, value in model_parameters.items():
        if key in scenario_defaults and key not in model_init_params:
            scenario_kwargs[key] = value
        else:
            kwargs[key] = value
    return kwargs, scenario_kwargs


def _build_model_init_kwargs(
    model: Model,
    model_parameters: dict[str, Any],
    *,
    add_scenario_when_empty: bool,
    require_model_accepts_scenario: bool,
) -> dict[str, Any]:
    """Build kwargs for model re-instantiation, splitting scenario/model params."""
    if not getattr(model, "scenario", None):
        return {**model_parameters}

    scenario = model.scenario
    scenario_class = type(scenario)
    scenario_defaults = _get_scenario_defaults(scenario)
    model_init_params = inspect.signature(type(model).__init__).parameters
    kwargs, scenario_kwargs = _split_scenario_params(
        model_parameters, scenario_defaults, model_init_params
    )

    has_kwargs = any(p.kind == p.VAR_KEYWORD for p in model_init_params.values())
    accepts_scenario = "scenario" in model_init_params or has_kwargs
    should_add_scenario = add_scenario_when_empty or bool(scenario_kwargs)

    if should_add_scenario and (accepts_scenario or not require_model_accepts_scenario):
        kwargs["scenario"] = scenario_class(**scenario_kwargs)
    return kwargs


def split_model_params(model_params):
    """Split model parameters into user-adjustable and fixed parameters.

    Args:
        model_params: Dictionary of all model parameters

    Returns:
        tuple: (user_adjustable_params, fixed_params)
    """
    model_params_input = {}
    model_params_fixed = {}
    for k, v in model_params.items():
        if check_param_is_fixed(v):
            model_params_fixed[k] = v
        else:
            model_params_input[k] = v
    return model_params_input, model_params_fixed


def check_param_is_fixed(param):
    """Check if a parameter is fixed (not user-adjustable).

    Args:
        param: Parameter to check

    Returns:
        bool: True if parameter is fixed, False otherwise
    """
    if isinstance(param, Slider):
        return False
    if not isinstance(param, dict):
        return True
    if "type" not in param:
        return True


def _resolve_init_signature(model_or_func):
    """Return ``(model, init parameters)`` for a model instance or an init function."""
    if inspect.isfunction(model_or_func) or inspect.ismethod(model_or_func):
        init_func = model_or_func
        model = None
    else:
        model = model_or_func
        init_func = type(model).__init__
    return model, inspect.signature(init_func).parameters


def _require_keyword_params(model_parameters) -> None:
    """Raise when the init function takes positional-only or ``*args`` parameters."""
    has_non_keyword_param = any(
        param.kind in _NON_KEYWORD_PARAM_KINDS for param in model_parameters.values()
    )
    if has_non_keyword_param:
        raise ValueError(
            "Modelly's visualization requires the use of keyword arguments to ensure the parameters are passed to Solara correctly. Please ensure all model parameters are of form param=value"
        )


def _require_known_params(
    model_parameters, model_params, scenario_defaults, has_var_keyword
) -> None:
    """Raise on missing required parameters or on parameters the model does not take."""
    for name in model_parameters:
        if (
            model_parameters[name].default == inspect.Parameter.empty
            and name not in model_params
            and name not in _IMPLICIT_INIT_PARAMS
            and not has_var_keyword
        ):
            raise ValueError(f"Missing required model parameter: {name}")

    for name in model_params:
        if (
            name not in model_parameters
            and name not in scenario_defaults
            and name not in _ALWAYS_ACCEPTED_PARAMS
            and not has_var_keyword
        ):
            raise ValueError(f"Invalid model parameter: {name}")


def _check_model_params(model_or_func, model_params):
    """Check if model parameters are valid for the model's initialization function.

    Args:
        model_or_func: Model instance or its initialization function
        model_params: Dictionary of model parameters

    Raises:
        ValueError: If a parameter is not valid for the model's initialization function
    """
    model, model_parameters = _resolve_init_signature(model_or_func)
    _require_keyword_params(model_parameters)

    has_var_keyword = any(
        param.kind == inspect.Parameter.VAR_KEYWORD
        for param in model_parameters.values()
    )

    scenario_defaults = {}
    if model is not None and getattr(model, "scenario", None):
        scenario_defaults = _get_scenario_defaults(model.scenario)

    _require_known_params(
        model_parameters, model_params, scenario_defaults, has_var_keyword
    )
