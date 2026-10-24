"""Read a sensitivity analysis from a TOML file (what ``modelly sensitivity spec.toml`` runs).

The file reuses the experiment format; ``[sensitivity]`` picks the method::

    [experiment]
    model = "model.py:SIR"          # a Model class, or module:function of the parameters
    steps = 60
    replicates = 2
    seed = 1
    outputs = ["infected"]          # the first output is analysed
    store = "runs/sensitivity"      # optional

    [space]
    beta = { min = 0.1, max = 0.8 }
    gamma = { min = 0.05, max = 0.3 }
    population = 1000

    [sensitivity]
    method = "morris"               # oat, morris, sobol, pawn
    statistic = "max"               # last, max, min, mean, sum
    trajectories = 20               # the method's settings

    [run]
    executor = "processes"
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

from modelly.experiments.spec import (
    SpecError,
    model_reference,
    read_document,
    read_run,
    read_space,
    relative_path,
)
from modelly.experiments.tasks import resolve
from modelly.sensitivity.pawn import pawn
from modelly.sensitivity.screening import morris, oat
from modelly.sensitivity.study import is_model
from modelly.sensitivity.variance import sobol

METHODS: dict[str, Callable[..., Any]] = {
    "oat": oat,
    "morris": morris,
    "sobol": sobol,
    "pawn": pawn,
}
EXPERIMENT_KEYS = ("steps", "replicates", "seed")
STUDY_KEYS = {"statistic", "output"}


def _method(section: dict[str, Any], override: str | None) -> Callable[..., Any]:
    """The method ``[sensitivity]`` (or ``override``) names; its settings are checked."""
    name = section.pop("method", "morris")
    name = name if override is None else override
    function = METHODS.get(name)
    if function is None:
        raise SpecError(
            f"sensitivity.method must be one of {sorted(METHODS)}, got {name!r}"
        )
    accepted = set(inspect.signature(function).parameters) | STUDY_KEYS
    unknown = set(section) - accepted
    if unknown:
        raise SpecError(f"{name} takes no setting(s) {sorted(unknown)}")
    return function


def load_sensitivity(
    path: str | Path, method: str | None = None
) -> tuple[Callable[..., Any], dict[str, Any]]:
    """The method a TOML file (or ``method``) names and every keyword argument for it."""
    document, base = read_document(path)
    table = document.get("experiment", {})
    if "model" not in table:
        raise SpecError(f"{path}: [experiment] needs model = 'path/model.py:Class'")
    section = dict(document.get("sensitivity", {}))
    function = _method(section, method)
    reference = model_reference(table["model"], base)
    model = reference if is_model(resolve(reference)) else resolve(reference)
    outputs = table.get("outputs", [])
    output = section.pop("output", outputs[0] if outputs else None)
    arguments = {"model": model, "space": read_space(document), "output": output}
    arguments |= section | {key: table[key] for key in EXPERIMENT_KEYS if key in table}
    if "store" in table:
        arguments["store"] = relative_path(table["store"], base)
    run = read_run(document, "serial")
    arguments |= {"executor": run.executor, "max_parallel": run.max_parallel}
    return function, arguments | {"options": run.options}
