"""Read an experiment from a TOML file (what ``modelly experiment run spec.toml`` runs).

Example spec::

    [experiment]
    model = "model.py:Epidemic"     # relative to this file, or package.module:Class
    steps = 365
    replicates = 20
    seed = 7
    outputs = ["infected", "recovered"]
    store = "runs/epidemic"         # relative to this file
    on_error = "record"             # or "skip", "raise"
    retries = 1

    [space]
    beta = { min = 0.05, max = 0.5 }          # a range (log = true, integer = true)
    vaccination = [0.0, 0.2, 0.4]             # a choice
    population = 10000                        # a fixed value

    [design]
    kind = "latin_hypercube"        # full_factorial (levels), sobol, halton (n), custom (points)
    n = 200

    [run]
    executor = "processes"
    max_parallel = 8
    [run.options]                   # passed to the executor (queue, walltime, address...)
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from modelly.experiments.designs import DESIGNS, Design
from modelly.experiments.experiment import DEFAULT_EXECUTOR, DEFAULT_STORE, Experiment
from modelly.experiments.space import Range, ScenarioSpace
from modelly.experiments.tasks import REFERENCE

EXPERIMENT_KEYS = ("steps", "replicates", "seed", "outputs", "on_error", "retries")
RANGE_KEYS = {"min", "max", "log", "integer"}
DESIGN_ARGUMENTS = {"full_factorial": "levels", "custom": "points"}
DEFAULT_DESIGN_ARGUMENT = "n"


class SpecError(ValueError):
    """The experiment file is missing a value or has one of the wrong kind."""


@dataclass
class RunSettings:
    """The ``[run]`` table: executor, parallelism and executor options."""

    executor: str = DEFAULT_EXECUTOR
    max_parallel: int | None = None
    options: dict[str, Any] = field(default_factory=dict)


def _relative(path: str, base: Path) -> str:
    """``path`` resolved against the spec's folder unless absolute."""
    candidate = Path(path)
    return str(candidate if candidate.is_absolute() else (base / candidate).resolve())


def _model(target: str, base: Path) -> str:
    """The model reference, a ``.py`` source made relative to the spec's folder."""
    source, sep, name = target.rpartition(REFERENCE)
    if not sep:
        raise SpecError(
            f"model must be path/model.py:Class or module:Class, got {target!r}"
        )
    if source.endswith(".py"):
        source = _relative(source, base)
    return f"{source}{REFERENCE}{name}"


def _dimension(name: str, value: Any) -> Any:
    """A TOML value as a space dimension: a range table, a choice list or fixed."""
    if not isinstance(value, Mapping):
        return value
    unknown = set(value) - RANGE_KEYS
    if unknown or not {"min", "max"} <= set(value):
        raise SpecError(
            f"space.{name}: a range is {{ min = .., max = .. }}, got {dict(value)}"
        )
    return Range(
        value["min"],
        value["max"],
        log=value.get("log", False),
        integer=value.get("integer", False),
    )


def _design(table: Mapping[str, Any]) -> Design:
    """The ``[design]`` table as a Design."""
    table = dict(table)
    kind = table.pop("kind", "full_factorial")
    if kind not in DESIGNS:
        raise SpecError(f"design.kind must be one of {sorted(DESIGNS)}, got {kind!r}")
    argument = DESIGN_ARGUMENTS.get(kind, DEFAULT_DESIGN_ARGUMENT)
    if set(table) - {argument}:
        raise SpecError(f"design {kind} takes {argument!r}, got {sorted(table)}")
    return DESIGNS[kind](table[argument]) if argument in table else DESIGNS[kind]()


def load_spec(path: str | Path) -> tuple[Experiment, RunSettings]:
    """The Experiment a TOML file describes, and its ``[run]`` settings."""
    path = Path(path)
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    base = path.resolve().parent
    table = document.get("experiment", {})
    if "model" not in table:
        raise SpecError(f"{path}: [experiment] needs model = 'path/model.py:Class'")
    space = ScenarioSpace(
        {
            name: _dimension(name, value)
            for name, value in document.get("space", {}).items()
        }
    )
    settings = {key: table[key] for key in EXPERIMENT_KEYS if key in table}
    experiment = Experiment(
        model=_model(table["model"], base),
        space=space,
        design=_design(document.get("design", {})),
        store=_relative(table.get("store", DEFAULT_STORE), base),
        **settings,
    )
    run = document.get("run", {})
    options = dict(run.get("options", {}))
    executor = run.get("executor", DEFAULT_EXECUTOR)
    return experiment, RunSettings(executor, run.get("max_parallel"), options)
