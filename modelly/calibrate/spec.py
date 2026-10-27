"""Read a calibration from a TOML file (what ``modelly calibrate spec.toml`` runs).

The file reuses the experiment format (``[experiment]``, ``[space]``,
``[run]``) and adds the priors, the targets and the method::

    [experiment]
    model = "model.py:SIR"          # relative to this file, or package.module:Class
    steps = 40
    replicates = 1
    seed = 7
    store = "runs/calibration"      # optional; a temporary folder otherwise

    [space]                         # a range is a uniform prior (log = true: log-uniform),
    beta = { min = 0.05, max = 1.0 }  # an integer range or a list a choice,
    population = 1000               # anything else a fixed parameter

    [priors]                        # optional: other priors, by kind
    gamma = { kind = "log_normal", mu = -2.3, sigma = 0.5 }

    [[targets]]
    name = "infected"
    file = "cases.csv"              # or observed = [..]; column defaults to name
    column = "cases"
    distance = "rmse"               # or mae, euclidean, wasserstein, module:function
    weight = 1.0

    [calibration]
    method = "abc_smc"              # abc_rejection, simulated_moments, bayes_opt, external_bayes_opt
    particles = 100                 # the method's settings
    budget = 3000                   # and its run() arguments

    [run]
    executor = "processes"
    max_parallel = 4
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from modelly.calibrate.base import Calibration
from modelly.calibrate.bayesopt import BayesOpt
from modelly.calibrate.external import ExternalBayesOpt
from modelly.calibrate.moments import SimulatedMoments
from modelly.calibrate.priors import Prior
from modelly.calibrate.rejection import ABCRejection
from modelly.calibrate.smc import ABCSMC
from modelly.calibrate.targets import Target
from modelly.experiments.space import Choice, Fixed, Range
from modelly.experiments.spec import (
    RunSettings,
    SpecError,
    model_reference,
    read_document,
    read_run,
    read_space,
    relative_path,
)
from modelly.experiments.tasks import REFERENCE, resolve

METHODS: dict[str, type[Calibration]] = {
    "abc_smc": ABCSMC,
    "abc_rejection": ABCRejection,
    "simulated_moments": SimulatedMoments,
    "bayes_opt": BayesOpt,
    "external_bayes_opt": ExternalBayesOpt,
}
EXPERIMENT_KEYS = ("steps", "replicates", "seed")
TARGET_KEYS = {
    "name",
    "observed",
    "file",
    "column",
    "distance",
    "weight",
    "summary",
    "output",
}


def _prior(value: Range | Choice | Fixed) -> Prior | None:
    """The prior a ``[space]`` dimension implies; None for a fixed value."""
    if isinstance(value, Fixed):
        return None
    if isinstance(value, Choice):
        return Prior.choice(value.values)
    if value.integer:
        return Prior.choice(list(range(int(value.low), int(value.high) + 1)))
    factory = Prior.log_uniform if value.log else Prior.uniform
    return factory(value.low, value.high)


def _declared_prior(name: str, table: Mapping[str, Any]) -> Prior:
    """A ``[priors]`` entry: ``kind`` and the class method's arguments."""
    arguments = dict(table)
    kind = arguments.pop("kind", None)
    factory = getattr(Prior, str(kind), None)
    if kind is None or not callable(factory) or kind.startswith("_"):
        raise SpecError(
            f"priors.{name}: kind must name a Prior class method, got {kind!r}"
        )
    try:
        return factory(**arguments)
    except TypeError as error:
        raise SpecError(f"priors.{name}: {error}") from error


def priors_and_fixed(
    document: Mapping[str, Any],
) -> tuple[dict[str, Prior], dict[str, Any]]:
    """The priors (from ``[space]`` and ``[priors]``) and the fixed parameters."""
    priors, fixed = {}, {}
    for name, dimension in read_space(document).parameters.items():
        prior = _prior(dimension)
        if prior is None:
            fixed[name] = dimension.value
        else:
            priors[name] = prior
    for name, table in document.get("priors", {}).items():
        fixed.pop(name, None)
        priors[name] = _declared_prior(name, table)
    return priors, fixed


def _function(value: Any) -> Any:
    """A ``module:function`` reference resolved; anything else unchanged."""
    return resolve(value) if isinstance(value, str) and REFERENCE in value else value


def _target(table: Mapping[str, Any], base: Path) -> Target:
    """One ``[[targets]]`` entry as a Target."""
    unknown = set(table) - TARGET_KEYS
    if unknown or "name" not in table:
        raise SpecError(f"a target needs name and takes {sorted(TARGET_KEYS)}")
    settings = {key: table[key] for key in ("weight", "output") if key in table}
    for key in ("distance", "summary"):
        if key in table:
            settings[key] = _function(table[key])
    observed = table.get("observed")
    if "file" in table:
        frame = pd.read_csv(relative_path(table["file"], base), encoding="utf-8")
        observed = frame[table.get("column", table["name"])].to_numpy(float)
    if observed is None:
        raise SpecError(f"target {table['name']!r} needs observed = [..] or file = ..")
    return Target(table["name"], observed, **settings)


def _split(method: type[Calibration], table: Mapping[str, Any]) -> tuple[dict, dict]:
    """``[calibration]`` keys as constructor settings and ``run()`` arguments."""
    run_keys = set(inspect.signature(method.run).parameters) - {
        "self",
        "executor",
        "options",
    }
    known = run_keys | set(inspect.signature(method.__init__).parameters)
    unknown = set(table) - known - {"method"}
    if unknown:
        raise SpecError(f"{method.__name__} takes no setting(s) {sorted(unknown)}")
    run = {k: v for k, v in table.items() if k in run_keys}
    settings = {k: v for k, v in table.items() if k not in run_keys and k != "method"}
    return settings, run


def load_calibration(
    path: str | Path,
) -> tuple[Calibration, dict[str, Any], RunSettings]:
    """The calibration a TOML file describes, its ``run()`` arguments and ``[run]`` settings."""
    document, base = read_document(path)
    table = document.get("experiment", {})
    if "model" not in table:
        raise SpecError(f"{path}: [experiment] needs model = 'path/model.py:Class'")
    section = dict(document.get("calibration", {}))
    name = section.get("method", "abc_smc")
    method = METHODS.get(name)
    if method is None:
        raise SpecError(
            f"calibration.method must be one of {sorted(METHODS)}, got {name!r}"
        )
    settings, run = _split(method, section)
    priors, fixed = priors_and_fixed(document)
    targets = [_target(entry, base) for entry in document.get("targets", [])]
    settings |= {key: table[key] for key in EXPERIMENT_KEYS if key in table}
    if "store" in table:
        settings["store"] = relative_path(table["store"], base)
    model = model_reference(table["model"], base)
    calibration = method(model, priors, targets, fixed=fixed, **settings)
    return calibration, run, read_run(document, "serial")
