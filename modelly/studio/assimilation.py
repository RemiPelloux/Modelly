"""Data assimilation from Studio: a particle filter or an ensemble Kalman filter, traced.

``assimilate`` runs one of the ``modelly.stream`` filters over an ensemble of the session's
model against a table of observations (a CSV file with a ``time`` column and one column per
observed reporter), and keeps what the dashboard shows at every observation:

- ``bands``: the filtered band of every reporter (the long-format frame of
  ``Ensemble.band``);
- ``history``: the filter's own history: the effective sample size, whether it resampled
  and the log evidence for the particle filter; each parameter's mean and spread for the
  ensemble Kalman filter;
- ``weights``: for the particle filter, each replicate's weight once the observation is
  taken into account, before any resampling (one row per observation, one column per
  replicate).

The weights are those the filter computes (prior weight times Gaussian likelihood,
normalised); they are read before ``assimilate`` resamples, so the trace shows the
degeneracy the effective sample size measures.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

import modelly.stream.sources as sources
from modelly.stream.kalman import EnsembleKalmanFilter
from modelly.stream.particle import DEFAULT_THRESHOLD, ParticleFilter
from modelly.studio.ensembles import (
    DEFAULT_REPLICATES,
    ensemble_of,
    reporter_operator,
)

if TYPE_CHECKING:
    from modelly.studio.session import StudioSession

PARTICLE, KALMAN = "particle filter", "ensemble Kalman filter"
METHODS = (PARTICLE, KALMAN)
DEFAULT_SD = 1.0
DEFAULT_SPREAD = 0.5
# Model attributes that are floats but no parameter.
CLOCK = frozenset({"time"})


@dataclass(frozen=True)
class FilterSettings:
    """How Studio assimilates the observations.

    Attributes:
        method: ``particle filter`` or ``ensemble Kalman filter``.
        replicates: The ensemble size.
        sd: The observation error, one standard deviation for every quantity.
        threshold: The particle filter resamples when the ESS falls below this fraction
            of the ensemble size.
        parameters: The model attributes the ensemble Kalman filter adjusts.
        spread: Each adjusted attribute starts uniform within this fraction of its value.
    """

    method: str = PARTICLE
    replicates: int = DEFAULT_REPLICATES
    sd: float = DEFAULT_SD
    threshold: float = DEFAULT_THRESHOLD
    parameters: tuple[str, ...] = ()
    spread: float = DEFAULT_SPREAD


@dataclass
class Assimilation:
    """What one filter run left: the bands, its history and the weights over time."""

    method: str
    bands: pd.DataFrame
    history: pd.DataFrame
    observations: pd.DataFrame
    weights: pd.DataFrame = field(default_factory=pd.DataFrame)


def read_observations(path: str | Path) -> list[sources.Observation]:
    """Every observation of a CSV file with a ``time`` column, in time order."""
    return sources.CSVSource(path).poll()


def observation_frame(observations: Sequence[sources.Observation]) -> pd.DataFrame:
    """The observations long-format: one row per time and quantity (``value``)."""
    rows = [
        {"time": o.time, "quantity": name, "value": value}
        for o in observations
        for name, value in o.values.items()
    ]
    return pd.DataFrame(rows, columns=["time", "quantity", "value"])


def posterior_weights(
    pf: ParticleFilter, observation: sources.Observation
) -> np.ndarray:
    """The weights ``pf`` gives its replicates for ``observation``, before resampling."""
    pf.ensemble.advance(observation.time)
    likelihood = np.array(
        [pf.operator.log_likelihood(m, observation, pf.sd) for m in pf.ensemble]
    )
    likelihood[np.isnan(likelihood)] = -np.inf
    log_weights = np.log(pf.weights) + likelihood
    log_weights -= np.max(log_weights)
    weights = np.exp(log_weights)
    return weights / weights.sum()


def _uniform(low: float, high: float, rng: np.random.Generator) -> float:
    """One draw, uniform between ``low`` and ``high``."""
    return float(rng.uniform(low, high))


def kalman_prior(session: StudioSession, settings: FilterSettings) -> dict:
    """A uniform start within ``spread`` of each adjusted attribute's live value."""
    prior = {}
    for name in settings.parameters:
        value = float(getattr(session.model, name))
        half = abs(value) * settings.spread
        prior[name] = partial(_uniform, value - half, value + half)
    return prior


def _particle(session, settings, observations) -> Assimilation:
    """Run the particle filter, keeping the band and the weights at each observation."""
    ensemble = ensemble_of(session, settings.replicates)
    operator = reporter_operator(ensemble[0])
    pf = ParticleFilter(ensemble, operator, settings.sd, threshold=settings.threshold)
    bands, weights = [], []
    for observation in observations:
        weights.append(posterior_weights(pf, observation))
        pf.assimilate(observation)
        bands.append(pf.band())
    times = [o.time for o in observations]
    table = pd.DataFrame(np.array(weights), index=pd.Index(times, name="time"))
    frame = observation_frame(observations)
    return Assimilation(PARTICLE, pd.concat(bands), pf.history, frame, table)


def _kalman(session, settings, observations) -> Assimilation:
    """Run the ensemble Kalman filter, keeping the band at each observation."""
    if not settings.parameters:
        raise ValueError(
            "choose at least one parameter for the Kalman filter to adjust"
        )
    ensemble = ensemble_of(
        session, settings.replicates, prior=kalman_prior(session, settings)
    )
    operator = reporter_operator(ensemble[0])
    enkf = EnsembleKalmanFilter(ensemble, operator, settings.sd, settings.parameters)
    bands = []
    for observation in observations:
        enkf.assimilate(observation)
        bands.append(ensemble.band(operator))
    frame = observation_frame(observations)
    return Assimilation(KALMAN, pd.concat(bands), enkf.history, frame)


def assimilate(
    session: StudioSession,
    observations: Sequence[sources.Observation],
    settings: FilterSettings | None = None,
) -> Assimilation:
    """Run the filter ``settings`` names over ``observations``, from the panel's values.

    Raises:
        ValueError: For an unknown method, no observations, or a Kalman filter with no
            parameter to adjust.
    """
    settings = settings or FilterSettings()
    if not observations:
        raise ValueError("there are no observations to assimilate")
    runners = {PARTICLE: _particle, KALMAN: _kalman}
    if settings.method not in runners:
        raise ValueError(f"method must be one of {METHODS}, got {settings.method!r}")
    return runners[settings.method](session, settings, list(observations))


def adjustable(session: StudioSession) -> list[str]:
    """The live model's float attributes, but its clock: what the Kalman filter can adjust."""
    return sorted(
        name
        for name, value in vars(session.model).items()
        if not name.startswith("_") and name not in CLOCK and type(value) is float
    )


__all__ = [
    "KALMAN",
    "METHODS",
    "PARTICLE",
    "Assimilation",
    "FilterSettings",
    "adjustable",
    "assimilate",
    "kalman_prior",
    "observation_frame",
    "posterior_weights",
    "read_observations",
]
