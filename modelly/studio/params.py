"""The parameter panel's fields, read from a model's ``Scenario`` and constructor.

Every field of the Scenario class the model's ``scenario`` argument defaults to, and every
keyword its constructor takes with a default, becomes a ``Parameter``. Its kind picks the
widget: ``bool`` a checkbox, a ``Literal`` or an ``Enum`` a select, a float between 0 and 1
a slider, another number a number field, a string a text field. Anything else (a tuple, a
dict, None) is shown but cannot be changed from the panel.
"""

from __future__ import annotations

import enum
import inspect
import typing
from dataclasses import dataclass
from typing import Any

from modelly.core.model import Model
from modelly.profile.loader import scenario_class

BOOL, INT, FLOAT, FRACTION, CHOICE, TEXT, FIXED = (
    "bool",
    "int",
    "float",
    "fraction",
    "choice",
    "text",
    "fixed",
)
EDITABLE = frozenset({BOOL, INT, FLOAT, FRACTION, CHOICE, TEXT})
# Constructor arguments that are not model parameters.
NOT_PARAMETERS = frozenset({"self", "scenario", "rng", "seed"})
FRACTION_STEP = 0.01


@dataclass(frozen=True)
class Parameter:
    """One field of the parameter panel.

    Attributes:
        name: The scenario field or constructor keyword.
        kind: The widget: one of ``bool``, ``int``, ``float``, ``fraction`` (a 0 to 1
            slider), ``choice``, ``text`` or ``fixed`` (shown, not editable).
        default: The value the model is built with unless it is changed.
        choices: The values a ``choice`` offers.
    """

    name: str
    kind: str
    default: Any
    choices: tuple = ()

    @property
    def editable(self) -> bool:
        """Whether the panel lets the value be changed."""
        return self.kind in EDITABLE


def _choices(annotation: Any) -> tuple:
    """The values a ``Literal`` or ``Enum`` annotation allows, else ``()``."""
    if typing.get_origin(annotation) is typing.Literal:
        return typing.get_args(annotation)
    if inspect.isclass(annotation) and issubclass(annotation, enum.Enum):
        return tuple(annotation)
    return ()


def kind_of(value: Any, annotation: Any = None) -> tuple[str, tuple]:
    """The widget kind for ``value`` and, for a ``choice``, the values it offers."""
    choices = _choices(annotation)
    if choices:
        return CHOICE, choices
    if isinstance(value, bool):
        return BOOL, ()
    if isinstance(value, int):
        return INT, ()
    if isinstance(value, float):
        return (FRACTION if 0.0 <= value <= 1.0 else FLOAT), ()
    if isinstance(value, str):
        return TEXT, ()
    return FIXED, ()


def _annotations(owner: type) -> dict[str, Any]:
    """The resolved annotations of ``owner``, or the raw ones when they do not resolve."""
    try:
        return typing.get_type_hints(owner)
    except (NameError, TypeError):
        return dict(getattr(owner, "__annotations__", {}))


def _scenario_parameters(model_class: type[Model]) -> list[Parameter]:
    """One parameter per field of the model's Scenario class."""
    parameters = dict(inspect.signature(model_class).parameters)
    scenario = scenario_class(parameters)
    if scenario is None:
        return []
    hints = _annotations(scenario)
    found = []
    for name, default in scenario._scenario_defaults.items():
        if name in NOT_PARAMETERS:  # the seed has its own field
            continue
        kind, choices = kind_of(default, hints.get(name))
        found.append(Parameter(name, kind, default, choices))
    return found


def _constructor_parameters(model_class: type[Model]) -> list[Parameter]:
    """One parameter per keyword with a default the constructor takes."""
    found = []
    for name, param in inspect.signature(model_class).parameters.items():
        if name in NOT_PARAMETERS or param.default is inspect.Parameter.empty:
            continue
        kind, choices = kind_of(param.default, param.annotation)
        found.append(Parameter(name, kind, param.default, choices))
    return found


def parameters_of(model_class: type[Model]) -> list[Parameter]:
    """The panel's fields for ``model_class``: its constructor's, then its Scenario's."""
    own = _constructor_parameters(model_class)
    names = {p.name for p in own}
    return own + [p for p in _scenario_parameters(model_class) if p.name not in names]


__all__ = ["Parameter", "kind_of", "parameters_of"]
