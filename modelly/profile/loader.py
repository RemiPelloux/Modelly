"""Find and build the model a ``python -m modelly.profile`` command line names."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any

from modelly.core.model import Model
from modelly.scenarios import Scenario

TARGET_MODULE = "_modelly_profile_target"
# Parameter names tried, in order, for the population when --size-param is not given.
SIZE_PARAMS = ("n", "N", "num_agents", "population")
VARIADIC = (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)


class TargetError(ValueError):
    """The command line names a model that cannot be loaded or built."""


def parse_param(text: str) -> tuple[str, Any]:
    """``key=value`` to ``(key, value)``; the value is a Python literal or else a string."""
    key, sep, raw = text.partition("=")
    if not sep or not key.strip():
        raise TargetError(f"--param expects key=value, got {text!r}")
    try:
        value = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        value = raw
    return key.strip(), value


def _module(source: str) -> Any:
    """Import ``source``: a ``.py`` file (its folder goes on sys.path) or a dotted module."""
    path = Path(source)
    if path.suffix != ".py":
        try:
            return importlib.import_module(source)
        except ImportError as error:
            raise TargetError(f"cannot import {source!r}: {error}") from error
    if not path.is_file():
        raise TargetError(f"no such file: {source}")
    sys.path.insert(0, str(path.resolve().parent))
    spec = importlib.util.spec_from_file_location(TARGET_MODULE, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[TARGET_MODULE] = module
    spec.loader.exec_module(module)
    return module


def load_class(target: str) -> type[Model]:
    """The Model subclass named by ``path/to/model.py:Class`` or ``package.module:Class``."""
    source, sep, name = target.rpartition(":")
    if not sep or not source or not name:
        raise TargetError(f"expected path/to/model.py:ModelClass, got {target!r}")
    cls = getattr(_module(source), name, None)
    if not (inspect.isclass(cls) and issubclass(cls, Model)):
        raise TargetError(f"{name!r} in {source} is not a Model subclass")
    return cls


def _scenario_class(parameters: dict[str, inspect.Parameter]) -> type[Scenario] | None:
    """The Scenario class a model's ``scenario`` argument defaults to, if any."""
    scenario = parameters.get("scenario")
    default = scenario.default if scenario is not None else None
    if inspect.isclass(default) and issubclass(default, Scenario):
        return default
    return None


def build_model(cls: type[Model], params: dict[str, Any], seed: int | None) -> Model:
    """Build ``cls``: parameters it takes by name go to it, the others to its scenario.

    The seed goes to the scenario when the model takes one, else to ``rng``.
    """
    parameters = dict(inspect.signature(cls).parameters)
    kwargs = {k: v for k, v in params.items() if k in parameters and k != "scenario"}
    rest = {k: v for k, v in params.items() if k not in kwargs}
    scenario = _scenario_class(parameters)
    if scenario is not None and (rest or seed is not None):
        seeded = {} if seed is None else {"rng": seed}
        kwargs["scenario"] = scenario(**seeded, **rest)
        rest = {}
    elif seed is not None:
        kwargs["rng"] = seed
    if rest:
        raise TargetError(f"{cls.__name__} takes no parameter(s) {sorted(rest)}")
    return cls(**kwargs)


def parameter_names(cls: type[Model]) -> set[str]:
    """The parameters ``cls`` takes by name, and those its Scenario class declares."""
    parameters = dict(inspect.signature(cls).parameters)
    own = {k for k, p in parameters.items() if p.kind not in VARIADIC}
    scenario = _scenario_class(parameters)
    declared = set(scenario._scenario_defaults) if scenario is not None else set()
    return (own | declared) - {"scenario", "rng"}


def size_param(cls: type[Model], name: str | None = None) -> str:
    """The parameter that sets the population: ``name``, else the first of SIZE_PARAMS taken."""
    if name is not None:
        return name
    known = parameter_names(cls)
    for candidate in SIZE_PARAMS:
        if candidate in known:
            return candidate
    raise TargetError(
        f"{cls.__name__} takes none of {', '.join(SIZE_PARAMS)}: name the parameter that "
        f"sets the population with --size-param (it takes {', '.join(sorted(known)) or 'none'})"
    )
