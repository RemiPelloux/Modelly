"""The 2.0 typed scenarios (epic H5), announced: what 1.5 warns about in a ``Scenario`` subclass.

In 2.0 a ``Scenario`` subclass is a typed base: its fields are its annotated attributes, a
value of the wrong type is refused, and a parameter it does not declare is an error. 1.5
keeps accepting all three and warns, naming the change to make:

* a public class attribute with no annotation (``beta = 0.3``): 2.0 will not see it as a field;
  write ``beta: float = 0.3``;
* a keyword the subclass does not declare (``MyScenario(betta=0.3)``): 2.0 refuses it;
  declare it as an annotated field, or fix the name;
* a value whose type does not match a plain annotation (``steps: int`` given ``"100"``): 2.0
  refuses it; pass a value of the annotated type. Only plain classes are checked (``int``,
  ``float``, ``bool``, ``str``, ``tuple``, ``list``, ``dict``); an ``int`` is a ``float`` and a
  numpy number is the Python number it stands for.

The plain ``Scenario(rng=42, density=0.8)`` with no subclass stays free-form.
"""

from __future__ import annotations

import numbers
import typing
import weakref
from typing import Any

from modelly._deprecation import deprecated

# deprecated() -> this module's function -> Scenario's hook -> the user's class or call.
_TO_USER = 3
NUMBERS = {int: numbers.Integral, float: numbers.Real}
PLAIN = (int, float, bool, str, tuple, list, dict)
# Resolved annotations per class: get_type_hints compiles them on every call.
_HINTS: weakref.WeakKeyDictionary[type, dict[str, Any]] = weakref.WeakKeyDictionary()


def _public_attributes(cls: type) -> list[str]:
    """Class attributes defined on ``cls`` that look like parameters: no methods, no dunders."""
    found = []
    for name, value in vars(cls).items():
        if name.startswith("_") or name in getattr(cls, "__annotations__", {}):
            continue
        if callable(value) or isinstance(value, (classmethod, staticmethod, property)):
            continue
        found.append(name)
    return found


def check_class(cls: type) -> None:
    """Warn for each attribute of a new subclass that 2.0 will not see as a field."""
    for name in _public_attributes(cls):
        value = getattr(cls, name)
        deprecated(
            f"{cls.__name__}.{name} without an annotation (2.0 typed scenarios do not take "
            "it as a field)",
            f"an annotated field, {name}: {type(value).__name__} = {value!r}",
            stacklevel=_TO_USER,
        )


def _hints(cls: type) -> dict[str, Any]:
    """The resolved annotations of ``cls``; empty when they cannot be resolved.

    A resolved result is kept per class; an unresolved one is not, so a name
    defined later still resolves on a later call.
    """
    found = _HINTS.get(cls)
    if found is None:
        try:
            found = typing.get_type_hints(cls)
        except (NameError, TypeError):
            return {}
        _HINTS[cls] = found
    return found


def _matches(value: Any, annotation: Any) -> bool:
    """Whether ``value`` fits a plain annotation (anything else is not checked)."""
    if annotation not in PLAIN:
        return True
    if annotation is bool:
        return isinstance(value, bool) or type(value).__name__ == "bool_"
    if annotation in NUMBERS and not isinstance(value, bool):
        return isinstance(value, NUMBERS[annotation])
    return isinstance(value, annotation)


def check_call(cls: type, defaults: dict[str, Any], kwargs: dict[str, Any]) -> None:
    """Warn for undeclared keywords and mistyped values of a typed subclass's instance."""
    if not defaults and not getattr(cls, "__annotations__", {}):
        return  # a subclass that declares nothing is free-form, as the plain Scenario
    hints = _hints(cls)
    declared = set(hints) | set(defaults)
    for name, value in kwargs.items():
        if name not in declared:
            deprecated(f"{cls.__name__}({name}=...), a parameter it does not declare",
                       f"an annotated field {name} on {cls.__name__}, or the declared name",
                       stacklevel=_TO_USER)  # fmt: skip
        elif not _matches(value, hints.get(name)):
            wanted = getattr(hints[name], "__name__", str(hints[name]))
            deprecated(f"{cls.__name__}({name}={value!r}), a {type(value).__name__} for a "
                       f"field annotated {wanted}", f"a {wanted} value", stacklevel=_TO_USER)  # fmt: skip


__all__ = ["check_call", "check_class"]
