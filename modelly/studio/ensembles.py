"""Replicates of the session's model, and the bands across them over time.

``ensemble_of`` builds a ``modelly.stream.Ensemble`` of the parameter panel's values: each
replicate gets a seed spawned from the panel's seed, as ``Scenario.spawn_replications``
hands them out. ``reporter_operator`` reads the DataCollector's numeric model reporters
from a replicate, so the bands and the filters need nothing written for Studio.
``band_series`` steps the ensemble and stacks ``Ensemble.band`` at every step: the
long-format frame (``time``, ``quantity``, ``mean``, ``q0.05``, ``q0.5``, ``q0.95``) the
ensemble view draws. It steps the replicates themselves, so it works for models that
cannot be checkpointed too.
"""

from __future__ import annotations

import inspect
import math
from collections.abc import Callable, Sequence
from functools import partial
from typing import TYPE_CHECKING, Any

import pandas as pd

from modelly.profile.loader import scenario_class
from modelly.scenarios import Scenario
from modelly.stream.bands import DEFAULT_QUANTILES
from modelly.stream.ensemble import Ensemble, Prior
from modelly.stream.operators import ObservationOperator
from modelly.studio.data import model_series

if TYPE_CHECKING:
    from modelly.core.model import Model
    from modelly.studio.session import StudioSession

DEFAULT_REPLICATES = 20
DEFAULT_ENSEMBLE_STEPS = 50


class NoReportersError(ValueError):
    """The model collects no numeric model reporter for a band or a filter to read."""


def latest_value(name: str, model: Model) -> float:
    """The last value the model's DataCollector collected for ``name``; NaN before any."""
    collected = model.datacollector.model_vars[name]
    return float(collected[-1]) if collected else math.nan


def reporter_operator(model: Model) -> ObservationOperator:
    """An observation operator over the model's numeric model reporters.

    Raises:
        NoReportersError: When the model collects none.
    """
    frame = model_series(model)
    if frame is None:
        raise NoReportersError(
            "the model collects no numeric model reporter: give it a DataCollector"
        )
    readers = {str(name): partial(latest_value, name) for name in frame.columns}
    return ObservationOperator(**readers)


def _seeded(model_class: type[Model], kwargs: dict[str, Any], scenario: Scenario):
    """``model_class(**kwargs)`` seeded from ``scenario``, for models without a Scenario."""
    return model_class(**kwargs, rng=scenario.seed_sequence)


def factory_and_scenario(
    model_class: type[Model], values: dict[str, Any], seed: int
) -> tuple[Callable[..., Model], Scenario]:
    """What ``Ensemble`` builds replicates with: a factory and the scenario to replicate.

    Constructor keywords go to the factory, the other values to the model's Scenario
    class; a model without one gets a plain ``Scenario`` that carries the seed.
    """
    parameters = dict(inspect.signature(model_class).parameters)
    kwargs = {k: v for k, v in values.items() if k in parameters}
    rest = {k: v for k, v in values.items() if k not in kwargs}
    owner = scenario_class(parameters)
    if owner is None:
        return partial(_seeded, model_class, kwargs), Scenario(rng=seed)
    return partial(model_class, **kwargs), owner(rng=seed, **rest)


def ensemble_of(
    session: StudioSession, replicates: int, prior: Prior | None = None
) -> Ensemble:
    """``replicates`` models with the panel's values, seeds spawned from the panel's seed."""
    factory, scenario = factory_and_scenario(
        session.model_class, session.values, session.seed
    )
    return Ensemble(factory, scenario, replicates, prior=prior)


def band_series(
    ensemble: Ensemble,
    steps: int,
    operator: ObservationOperator | None = None,
    quantiles: Sequence[float] = DEFAULT_QUANTILES,
) -> pd.DataFrame:
    """The band of ``operator`` now and after each of ``steps`` steps, stacked.

    ``operator`` defaults to the first replicate's numeric model reporters. The
    replicates are stepped in place.
    """
    operator = operator or reporter_operator(ensemble[0])
    start = ensemble.time
    frames = [ensemble.band(operator, quantiles)]
    for step in range(1, steps + 1):
        ensemble.advance(start + step)
        frames.append(ensemble.band(operator, quantiles))
    return pd.concat(frames, ignore_index=True)


def session_bands(
    session: StudioSession,
    replicates: int = DEFAULT_REPLICATES,
    steps: int = DEFAULT_ENSEMBLE_STEPS,
) -> pd.DataFrame:
    """The band of the model reporters across ``replicates`` new runs of the panel's values."""
    return band_series(ensemble_of(session, replicates), steps)


__all__ = [
    "NoReportersError",
    "band_series",
    "ensemble_of",
    "factory_and_scenario",
    "latest_value",
    "reporter_operator",
    "session_bands",
]
