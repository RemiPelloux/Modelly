"""Ensemble Kalman filter for continuous parameters (state/parameter augmentation).

The stochastic ensemble Kalman filter of Evensen (1994, 2003) with perturbed
observations (Burgers, van Leeuwen & Evensen 1998). The quantities it adjusts
are named model attributes: parameters such as a contact rate, or any
continuous state the model reads back. At each observation the replicates
run to its time; with ``X`` the attributes (one row per replicate), ``Y``
what the operator reads from each and ``R`` the observation error variance::

    K   = cov(X, Y) (cov(Y, Y) + R)^-1
    X_i = X_i + K (y + e_i - Y_i),      e_i ~ N(0, R)

Agent-level state is left alone: an agent-based model is rarely a vector the
filter could shift, so the attributes are where it learns. Parameters can be
kept in a range with ``bounds``, clipping after each update::

    enkf = EnsembleKalmanFilter(ensemble, observe, sd=4.0, parameters=["beta"],
                                bounds={"beta": (0.0, 2.0)})
    enkf.run(source)
    enkf.estimate()                      # {"beta": 0.31}, the ensemble mean

The perturbations come from a generator derived from the scenario's seed, so
the filter is deterministic for a seed.

References:
    Evensen, G. (1994). Sequential data assimilation with a nonlinear
    quasi-geostrophic model using Monte Carlo methods to forecast error
    statistics. Journal of Geophysical Research, 99(C5), 10143-10162.
    Burgers, G., van Leeuwen, P. J. & Evensen, G. (1998). Analysis scheme in
    the ensemble Kalman filter. Monthly Weather Review, 126(6), 1719-1724.
    Evensen, G. (2003). The Ensemble Kalman Filter: theoretical formulation
    and practical implementation. Ocean Dynamics, 53(4), 343-367.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from modelly.stream.ensemble import KALMAN_DOMAIN, Ensemble
from modelly.stream.sources import Observation, due

if TYPE_CHECKING:
    from modelly.stream.operators import ObservationOperator

# Degrees of freedom removed from the ensemble covariance (unbiased estimate).
COVARIANCE_DDOF = 1


def enkf_update(
    states: np.ndarray,
    predicted: np.ndarray,
    observed: np.ndarray,
    variance: np.ndarray,
) -> np.ndarray:
    """The EnKF analysis of ``states`` (replicates by attributes).

    ``predicted`` holds what each replicate would observe (replicates by
    quantities), ``observed`` one perturbed observation per replicate (same
    shape) and ``variance`` the observation error variance of each quantity.
    """
    n = len(states)
    state_anomalies = states - states.mean(axis=0)
    predicted_anomalies = predicted - predicted.mean(axis=0)
    scale = 1.0 / (n - COVARIANCE_DDOF)
    cross = scale * state_anomalies.T @ predicted_anomalies
    innovation_cov = scale * predicted_anomalies.T @ predicted_anomalies
    innovation_cov += np.diag(variance)
    gain = np.linalg.solve(innovation_cov, cross.T).T
    return states + (observed - predicted) @ gain.T


class EnsembleKalmanFilter:
    """Stochastic EnKF with perturbed observations (Evensen 1994, 2003)."""

    def __init__(
        self,
        ensemble: Ensemble,
        operator: ObservationOperator,
        sd: float | Mapping[str, float],
        parameters: Sequence[str],
        *,
        bounds: Mapping[str, tuple[float, float]] | None = None,
    ) -> None:
        """Adjust the ``parameters`` attributes of ``ensemble`` to fit the observations.

        ``sd`` is the observation error, one standard deviation for every
        quantity or one per quantity. ``bounds`` maps a parameter to the
        ``(low, high)`` range it is clipped to after each update.
        """
        if not parameters:
            raise ValueError("the filter needs at least one parameter to adjust")
        unknown = set(bounds or {}) - set(parameters)
        if unknown:
            raise ValueError(f"bounds for attributes not adjusted: {sorted(unknown)}")
        self.ensemble = ensemble
        self.operator = operator
        self.sd = sd
        self.parameters = tuple(parameters)
        self.bounds = dict(bounds or {})
        self._noise = np.random.default_rng(ensemble.seed(KALMAN_DOMAIN))
        self._history: list[dict[str, float]] = []

    def states(self) -> np.ndarray:
        """The adjusted attributes: one row per replicate, one column per parameter."""
        return np.array(
            [[float(getattr(m, p)) for p in self.parameters] for m in self.ensemble]
        )

    def _set_states(self, states: np.ndarray) -> None:
        """Write ``states`` back to the replicates, clipped to the bounds."""
        for column, name in enumerate(self.parameters):
            low, high = self.bounds.get(name, (-np.inf, np.inf))
            states[:, column] = np.clip(states[:, column], low, high)
        for model, row in zip(self.ensemble, states):
            for name, value in zip(self.parameters, row):
                setattr(model, name, float(value))

    def _scales(self, names: Sequence[str]) -> np.ndarray:
        """The observation standard deviation of each of ``names``."""
        sd = self.sd
        scales = np.array(
            [float(sd[n] if isinstance(sd, Mapping) else sd) for n in names]
        )
        if np.any(scales <= 0):
            raise ValueError(f"standard deviations must be positive, got {scales}")
        return scales

    def assimilate(self, observation: Observation) -> dict[str, float]:
        """Run the ensemble to ``observation`` and update the parameters.

        Returns the ensemble mean of each parameter after the update; an
        observation with none of the operator's quantities changes nothing.
        """
        self.ensemble.advance(observation.time)
        names = [n for n in self.operator.names if n in observation.values]
        if names:
            readings = [self.operator(m) for m in self.ensemble]
            predicted = np.array([[r[n] for n in names] for r in readings])
            scales = self._scales(names)
            observed = np.array([observation.values[n] for n in names])
            noise = self._noise.normal(0.0, scales, size=predicted.shape)
            updated = enkf_update(self.states(), predicted, observed + noise, scales**2)
            self._set_states(updated)
        return self._record(observation.time)

    def _record(self, time: float) -> dict[str, float]:
        """Log the mean and spread of each parameter at ``time``; return the means."""
        states = self.states()
        means = dict(zip(self.parameters, (float(v) for v in states.mean(axis=0))))
        spreads = states.std(axis=0, ddof=COVARIANCE_DDOF)
        row = {"time": float(time), **means}
        row.update({f"{p}_sd": float(s) for p, s in zip(self.parameters, spreads)})
        self._history.append(row)
        return means

    def run(
        self, source: object | Iterable[Observation], until: float | None = None
    ) -> list[dict[str, float]]:
        """Assimilate every observation ``source`` has, up to ``until``.

        ``source`` is a stream source (anything with ``poll(until)``) or an
        iterable of observations in time order (see ``sources.due``).
        """
        return [self.assimilate(o) for o in due(source, until)]

    def estimate(self) -> dict[str, float]:
        """The ensemble mean of each parameter."""
        means = self.states().mean(axis=0)
        return dict(zip(self.parameters, (float(v) for v in means)))

    @property
    def history(self) -> pd.DataFrame:
        """One row per observation: time, then each parameter's mean and ``<name>_sd``."""
        columns = ["time", *self.parameters, *(f"{p}_sd" for p in self.parameters)]
        return pd.DataFrame(self._history, columns=columns)
