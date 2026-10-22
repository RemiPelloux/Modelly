"""Reporter plumbing for :class:`modelly.datacollection.DataCollector`.

A reporter is what the user hands the collector: an attribute name, a callable,
a bound method, a ``functools.partial`` or a ``[function, [params]]`` list. The
functions here normalise them once at registration and then gather values as
cheaply as possible on every ``collect``:

* attribute reporters are gathered with a single ``operator.attrgetter`` per
  agent, so the per-agent work happens in C;
* a value is copied only when it is mutable, so the common scalar case costs a
  set lookup instead of a ``deepcopy`` call.
"""

from __future__ import annotations

import types
from collections.abc import Callable, Iterable
from copy import deepcopy
from functools import partial
from operator import attrgetter
from typing import Any

import numpy as np

LIST_REPORTER_LENGTH = 2  # [function, [param_1, param_2]]

# Exact types that never need a defensive copy. ``issuperset`` over the row's
# types is one C call; subclasses (e.g. numpy scalars) fall back to isinstance.
_IMMUTABLE_TYPES = frozenset(
    {str, int, bool, float, complex, bytes, tuple, frozenset, type(None)}
)
_IMMUTABLE_BASES = (str, int, float, tuple, np.generic)


def snapshot(value: Any) -> Any:
    """Return ``value`` itself when immutable, otherwise a deep copy.

    Stored values must not change when the model mutates them on a later step.
    """
    if type(value) in _IMMUTABLE_TYPES or isinstance(value, _IMMUTABLE_BASES):
        return value
    return deepcopy(value)


def check_list_reporter(name: str, reporter: list) -> None:
    """Validate that a list-style reporter has the form [callable, [params]]."""
    if len(reporter) != LIST_REPORTER_LENGTH or not callable(reporter[0]):
        raise ValueError(
            f"Reporter '{name}' must use the format [function, [param1, param2]]. "
            f"Got: {reporter!r}"
        )
    if not isinstance(reporter[1], (list, tuple)):
        raise ValueError(
            f"Reporter '{name}' must use the format [function, [param1, param2]]. "
            f"The second element must be a list or tuple of parameters, got: {reporter[1]!r}"
        )


def validate_model_reporter(name: str, reporter: Any, model: Any) -> None:
    """Run a model reporter once so a broken definition fails loudly on first collect.

    Raises:
        ValueError: If reporter has an invalid list format
        AttributeError: If model attribute doesn't exist
        RuntimeError: If reporter execution fails
    """
    if isinstance(reporter, (types.LambdaType, partial)):
        try:
            reporter(model)
        except Exception as e:
            raise RuntimeError(
                f"Lambda reporter '{name}' failed validation: {e!s}\n"
                f"Example: lambda m: len(m.agents)"
            ) from e
    elif callable(reporter):
        try:
            reporter()
        except Exception as e:
            raise RuntimeError(
                f"Method reporter '{name}' failed validation: {e!s}"
            ) from e
    elif isinstance(reporter, str):
        if not hasattr(model, reporter):
            raise AttributeError(
                f"Model reporter '{name}' attribute validation failed: "
                f"Model reporter '{name}' references non-existent attribute '{reporter}'\n"
            )
    elif isinstance(reporter, list):
        check_list_reporter(name, reporter)


def collect_model_value(name: str, reporter: Any, model: Any) -> Any:
    """Evaluate one model reporter against ``model`` and return a stored-safe value.

    List reporters are re-checked on every call: the list is user-owned and may
    have been edited after validation.
    """
    if isinstance(reporter, types.LambdaType | partial):
        return snapshot(reporter(model))
    if isinstance(reporter, str):
        return snapshot(getattr(model, reporter, None))
    if isinstance(reporter, list):
        check_list_reporter(name, reporter)
        return snapshot(reporter[0](*reporter[1]))
    # Assume it's a callable otherwise (e.g., method)
    return snapshot(reporter())


def make_agent_reporter(name: str, reporter: Any) -> Callable[[Any], Any]:
    """Normalise an agent reporter definition into a one-argument callable.

    Attribute names become a getter that raises a descriptive AttributeError
    and carries the attribute in ``_modelly_attribute`` so collection can use
    the C fast path. ``[function, [params]]`` lists are bound. Anything else is
    already a suitable callable and is returned as is.
    """
    if isinstance(reporter, str):
        attribute = reporter

        def attr_reporter(agent):
            try:
                return getattr(agent, attribute)
            except AttributeError as e:
                raise AttributeError(
                    f"Agent {agent.unique_id} of type {type(agent).__name__} "
                    f"has no attribute '{attribute}' (reporter: '{name}')"
                ) from e

        attr_reporter._modelly_attribute = attribute
        return attr_reporter

    if isinstance(reporter, list):
        check_list_reporter(name, reporter)
        func, params = reporter

        def func_with_params(agent):
            return func(agent, *params)

        return func_with_params

    return reporter


def collect_agent_rows(
    agents: Iterable[Any], reporters: dict[str, Callable], time: float
) -> list[tuple]:
    """Return one ``(time, unique_id, *values)`` row per agent.

    ``agents`` must be re-iterable (any AgentSet is). When every reporter is an
    attribute name the values are gathered by one ``attrgetter`` call per agent;
    a missing attribute re-runs the generic path to produce the descriptive error.
    """
    attributes = [
        getattr(rep, "_modelly_attribute", None) for rep in reporters.values()
    ]
    if attributes and None not in attributes:
        try:
            return _collect_attribute_rows(agents, attributes, time)
        except AttributeError:
            pass
    return _collect_callable_rows(agents, tuple(reporters.values()), time)


def _collect_attribute_rows(
    agents: Iterable[Any], attributes: list[str], time: float
) -> list[tuple]:
    getter = attrgetter(*attributes)
    single = len(attributes) == 1
    immutable = _IMMUTABLE_TYPES.issuperset
    rows = []
    for agent in agents:
        values = (getter(agent),) if single else getter(agent)
        if not immutable(map(type, values)):
            values = tuple(map(snapshot, values))
        rows.append((time, agent.unique_id, *values))
    return rows


def _collect_callable_rows(
    agents: Iterable[Any], funcs: tuple[Callable, ...], time: float
) -> list[tuple]:
    immutable = _IMMUTABLE_TYPES.issuperset
    rows = []
    for agent in agents:
        values = [rep(agent) for rep in funcs]
        if not immutable(map(type, values)):
            values = map(snapshot, values)
        rows.append((time, agent.unique_id, *values))
    return rows
