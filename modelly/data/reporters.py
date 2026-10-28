"""Reporter plumbing for :class:`modelly.data.collector.DataCollector`.

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
from itertools import repeat
from operator import attrgetter
from typing import Any

import numpy as np

from modelly._native import sets
from modelly._native.sets import attr_values
from modelly.core.columns import ID_COLUMN

LIST_REPORTER_LENGTH = 2  # [function, [param_1, param_2]]

# Exact types that never need a defensive copy. ``issuperset`` over the row's
# types is one C call; subclasses (e.g. numpy scalars) fall back to isinstance.
_IMMUTABLE_TYPES = frozenset(
    {str, int, bool, float, complex, bytes, tuple, frozenset, type(None)}
)
_IMMUTABLE_BASES = (str, int, float, tuple, np.generic)
_unique_id = attrgetter("unique_id")


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


def compile_model_reporter(name: str, reporter: Any) -> Callable[[Any], Any]:
    """Turn a model reporter definition into a plain ``callable(model)``.

    The type dispatch happens here, once, instead of on every ``collect``.
    List reporters are re-checked on every call: the list is user-owned and
    may have been edited after validation.
    """
    if isinstance(reporter, types.LambdaType | partial):
        return reporter
    if isinstance(reporter, str):
        return partial(getattr_or_none, name=reporter)
    # Partials of module functions rather than closures, so models pickle.
    if isinstance(reporter, list):
        return partial(_call_list, name=name, reporter=reporter)
    return partial(_call_without_model, reporter=reporter)  # e.g. a bound method


def _call_list(model: Any, name: str, reporter: list) -> Any:
    """Call a ``[function, [params]]`` model reporter."""
    check_list_reporter(name, reporter)
    return reporter[0](*reporter[1])


def _call_without_model(model: Any, reporter: Callable[[], Any]) -> Any:
    """Call a reporter that takes no model argument, such as a bound method."""
    return reporter()


def getattr_or_none(model: Any, name: str) -> Any:
    """``getattr`` with a ``None`` default, as model attribute reporters have always behaved."""
    return getattr(model, name, None)


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
    # Partials of module functions rather than closures, so models pickle.
    if isinstance(reporter, str):
        attr_reporter = partial(_agent_attribute, attribute=reporter, name=name)
        attr_reporter._modelly_attribute = reporter
        return attr_reporter

    if isinstance(reporter, list):
        check_list_reporter(name, reporter)
        func, params = reporter
        return partial(_call_with_params, func=func, params=params)

    return reporter


def _agent_attribute(agent: Any, attribute: str, name: str) -> Any:
    """Read an agent attribute, naming the reporter when it is missing."""
    try:
        return getattr(agent, attribute)
    except AttributeError as e:
        raise AttributeError(
            f"Agent {agent.unique_id} of type {type(agent).__name__} "
            f"has no attribute '{attribute}' (reporter: '{name}')"
        ) from e


def _call_with_params(agent: Any, func: Callable[..., Any], params: list) -> Any:
    """Call a ``[function, [params]]`` agent reporter."""
    return func(agent, *params)


def collect_agent_rows(
    agents: Iterable[Any], reporters: dict[str, Callable], time: float
) -> list[tuple]:
    """Return one ``(time, unique_id, *values)`` row per agent.

    Values are gathered one reporter at a time over all agents (a C-level
    ``map`` per column) and the columns are zipped into rows, so the per-agent
    Python work is close to zero. A column is copied only if it holds a mutable
    value. Attribute reporters use one ``attrgetter``; a missing attribute
    re-runs the reporter's own getter to produce the descriptive error.

    When every reporter is a ``Column`` of the agents' single class and
    ``agents`` is that class's whole population, the rows are sliced straight
    out of the column table in table order, with no per-agent work at all.
    """
    agents = list(agents)
    funcs = tuple(reporters.values())
    attributes = [getattr(rep, "_modelly_attribute", None) for rep in funcs]
    table = _whole_column_table(agents, attributes)
    if table is not None:
        n = len(agents)
        ids = table._data[ID_COLUMN][:n].tolist()
        columns = [table._data[name][:n].tolist() for name in attributes]
    else:
        ids = list(map(_unique_id, agents))
        columns = _reporter_columns(agents, funcs, attributes)
    columns = [_snapshot_column(column) for column in columns]
    return list(zip(repeat(time), ids, *columns))


def _reporter_columns(
    agents: list[Any], funcs: tuple[Callable, ...], attributes: list[str | None]
) -> list[list]:
    """One list per reporter; attribute reporters share a single attrgetter pass."""
    if attributes and None not in attributes:
        try:
            return _attribute_columns(agents, attributes)
        except AttributeError:
            pass
    return [_reporter_column(agents, *pair) for pair in zip(funcs, attributes)]


def _attribute_columns(agents: list[Any], attributes: list[str]) -> list[list]:
    """One list per attribute: compiled, one gather per attribute, else one attrgetter pass.

    The compiled gather (``attr_values``) reads a Column attribute from its
    table without calling its Python getter, and plain attributes as attrgetter does.
    """
    if sets.NATIVE or len(attributes) == 1:
        return [attr_values(agents, name) for name in attributes]
    rows = map(attrgetter(*attributes), agents)
    return [list(column) for column in zip(*rows)]


def _reporter_column(
    agents: list[Any], reporter: Callable, attribute: str | None
) -> list:
    """The values of one reporter, an undotted attribute reporter by the compiled gather.

    A missing attribute runs the reporter itself, for its descriptive error.
    """
    if sets.NATIVE and attribute is not None and "." not in attribute:
        try:
            return attr_values(agents, attribute)
        except AttributeError:
            pass
    return list(map(reporter, agents))


def _whole_column_table(agents: list[Any], attributes: list[str | None]):
    """Return the column table when ``agents`` is one class's whole population.

    Requires every attribute to be a Column of that class; otherwise None.
    """
    if not agents or not attributes or None in attributes:
        return None
    specs = getattr(type(agents[0]), "_column_specs", None)
    if not specs or any(name not in specs for name in attributes):
        return None
    table = agents[0]._column_table
    if len(table) != len(agents) or len(set(map(type, agents))) != 1:
        return None
    return table


def _snapshot_column(column: list) -> list:
    """Copy the mutable values of a column; immutable columns are returned as is."""
    if _IMMUTABLE_TYPES.issuperset(map(type, column)):
        return column
    return [snapshot(value) for value in column]
