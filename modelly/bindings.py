"""Modelly for other languages: a few functions of plain values that return data frames.

The R package (``r/modelly``, through reticulate) and the Julia package
(``julia/Modelly.jl``, through PythonCall) call these functions rather than Modelly's classes,
so what crosses the language boundary is numbers, strings, lists, dictionaries and pandas
DataFrames, which both bridges convert to native data frames. A model is named by a target,
``path/to/model.py:Class`` or ``package.module:Class``.

R has no integer literal without ``L``, so every count, seed and step number is converted
with ``int()`` here, and a model parameter whose scenario field is annotated ``int`` is too:
``modelly_run("sir.py:Epidemic", population = 1000)`` works from R as written.
"""

from __future__ import annotations

import inspect
import typing
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from modelly.calibrate import Prior, Target
from modelly.profile.loader import build_model, load_class, scenario_class

PRIORS = ("uniform", "log_uniform", "normal", "log_normal")
SERIAL = "serial"


def _scenario(target: str) -> type | None:
    """The Scenario class of the model ``target`` names, if it takes one."""
    return scenario_class(dict(inspect.signature(load_class(target)).parameters))


def _fields(target: str) -> dict[str, tuple[Any, Any]]:
    """``{name: (annotation, default)}`` of the scenario's fields."""
    scenario = _scenario(target)
    if scenario is None:
        return {}
    hints = typing.get_type_hints(scenario)
    return {
        name: (hints.get(name), getattr(scenario, name))
        for name in hints
        if not name.startswith("_") and name != "rng" and hasattr(scenario, name)
    }


def _cast(target: str, params: Mapping[str, Any]) -> dict[str, Any]:
    """``params`` with every value of an ``int`` field made an ``int``, lists made tuples."""
    fields = _fields(target)
    out = {}
    for name, value in params.items():
        annotation = fields.get(name, (None, None))[0]
        if annotation is int:
            out[name] = int(value)
        else:
            out[name] = tuple(value) if isinstance(value, list) else value
    return out


def parameters(target: str) -> pd.DataFrame:
    """The model's scenario parameters: name, type and default, one row each."""
    rows = [
        {
            "name": name,
            "type": getattr(kind, "__name__", str(kind)),
            "default": repr(default),
        }
        for name, (kind, default) in _fields(target).items()
    ]
    return pd.DataFrame(rows, columns=["name", "type", "default"])


def model(target: str, params: Mapping[str, Any] | None = None, seed: int = 0) -> Any:
    """A built model (a Python object; its methods are callable from R and Julia)."""
    return build_model(load_class(target), _cast(target, params or {}), int(seed))


def simulate(
    target: str,
    params: Mapping[str, Any] | None = None,
    seed: int = 0,
    steps: int = 100,
) -> pd.DataFrame:
    """One run of ``steps`` steps: the model reporters per step, with a ``step`` column."""
    built = model(target, params, seed)
    built.run_for(int(steps))
    frame = built.datacollector.get_model_vars_dataframe().reset_index(drop=True)
    frame.insert(0, "step", range(len(frame)))
    return frame


def prior(spec: Any) -> Prior:
    """A prior from ``Prior`` itself or ``[kind, a, b]`` (``["uniform", 0.05, 1]``)."""
    if isinstance(spec, Prior):
        return spec
    kind, first, second = spec
    if kind not in PRIORS:
        raise ValueError(f"a prior is one of {PRIORS}, not {kind!r}")
    return getattr(Prior, kind)(float(first), float(second))


def calibrate(
    target: str, priors: Mapping[str, Any], observed: Mapping[str, Sequence[float]], *,
    steps: int, particles: int = 100, generations: int = 6, seed: int = 0,
    fixed: Mapping[str, Any] | None = None, executor: str = SERIAL,
) -> dict[str, pd.DataFrame]:  # fmt: skip
    """ABC-SMC: the posterior summary, its particles and the trace of the generations.

    ``observed`` maps a model reporter to its observed series, one value per step after the
    first. Runs are serial by default, since a language embedding Python has no script for
    worker processes to re-import.
    """
    from modelly.calibrate import ABCSMC  # noqa: PLC0415

    model_class = load_class(target)
    calibration = ABCSMC(
        model=model_class, priors={name: prior(spec) for name, spec in priors.items()},
        targets=[Target(name, observed=list(map(float, values))) for name, values in observed.items()],
        steps=int(steps), particles=int(particles), seed=int(seed),
        fixed=_cast(target, fixed or {}),
    )  # fmt: skip
    posterior = calibration.run(generations=int(generations), executor=executor)
    return {
        "summary": posterior.summary().reset_index(names="parameter"),
        "particles": posterior.to_dataframe(),
        "trace": calibration.trace(),
    }


__all__ = ["calibrate", "model", "parameters", "prior", "simulate"]
