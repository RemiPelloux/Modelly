"""Tests for the ensemble Kalman filter (modelly.stream.kalman)."""

import numpy as np
import pytest

from modelly import Model
from modelly.scenarios import Scenario
from modelly.stream import (
    Ensemble,
    EnsembleKalmanFilter,
    Observation,
    ObservationOperator,
    ReplaySource,
)
from modelly.stream.kalman import enkf_update

SEED = 11
LARGE = 2000
SMALL = 30
# Prior N(0, 1), observation 1 with error sd 1: the posterior is N(1/2, 1/2).
POSTERIOR_MEAN = 0.5
POSTERIOR_SD = np.sqrt(0.5)
MONTE_CARLO_TOLERANCE = 0.05


def _standard_normal(rng):
    """A draw from the N(0, 1) prior."""
    return rng.normal()


def _unit_uniform(rng):
    """A draw from the U(0, 1) prior."""
    return rng.uniform()


def _members(n, seed=SEED, prior=_standard_normal):
    """An ensemble of plain models carrying a parameter ``theta`` drawn from ``prior``."""
    return Ensemble(Model, Scenario(rng=seed), n, prior={"theta": prior})


def _theta():
    """An operator observing ``theta`` itself."""
    return ObservationOperator(level=lambda m: m.theta)


def test_the_linear_gaussian_posterior_is_recovered():
    """Observing the parameter directly, the analysis is the exact Kalman posterior."""
    enkf = EnsembleKalmanFilter(_members(LARGE), _theta(), sd=1.0, parameters=["theta"])
    means = enkf.assimilate(Observation(1.0, {"level": 1.0}))
    assert means["theta"] == pytest.approx(POSTERIOR_MEAN, abs=MONTE_CARLO_TOLERANCE)
    spread = enkf.states()[:, 0].std(ddof=1)
    assert spread == pytest.approx(POSTERIOR_SD, abs=MONTE_CARLO_TOLERANCE)
    assert enkf.ensemble.time == 1.0


def test_update_matches_the_scalar_kalman_gain():
    """One state, one quantity: x + P/(P+R) (d - x) for each replicate."""
    states = np.array([[0.0], [1.0], [2.0]])
    observed = np.array([[1.5], [1.0], [0.5]])
    updated = enkf_update(states, states.copy(), observed, np.array([1.0]))
    gain = 1.0 / (1.0 + 1.0)  # sample variance 1, observation variance 1
    np.testing.assert_allclose(updated, states + gain * (observed - states))


def test_bounds_clip_every_update():
    """A parameter is held to its range whatever the observation says."""
    enkf = EnsembleKalmanFilter(
        _members(SMALL, prior=_unit_uniform),
        _theta(),
        sd=0.1,
        parameters=["theta"],
        bounds={"theta": (0.0, 1.0)},
    )
    enkf.assimilate(Observation(1.0, {"level": -50.0}))
    assert enkf.states().min() == 0.0
    assert all(isinstance(m.theta, float) for m in enkf.ensemble)


def test_an_observation_without_the_quantities_changes_nothing():
    """The ensemble runs to the time; the parameters stay; a history row is logged."""
    enkf = EnsembleKalmanFilter(_members(SMALL), _theta(), sd=1.0, parameters=["theta"])
    before = enkf.states()
    enkf.assimilate(Observation(2.0, {"other": 3.0}))
    np.testing.assert_array_equal(enkf.states(), before)
    assert enkf.history["time"].tolist() == [2.0]
    assert list(enkf.history.columns) == ["time", "theta", "theta_sd"]


def test_the_filter_is_deterministic_for_a_seed():
    """Same seed, same perturbations and parameters; another seed differs."""

    def run(seed):
        """The parameter history of a filter over a few observations."""
        enkf = EnsembleKalmanFilter(
            _members(SMALL, seed), _theta(), sd=0.5, parameters=["theta"]
        )
        records = [{"time": t, "level": 0.3} for t in (1, 2, 3)]
        steps = enkf.run(ReplaySource(records), until=2)
        assert len(steps) == 2
        return enkf.history.to_numpy().tobytes(), enkf.estimate()

    assert run(SEED) == run(SEED)
    assert run(SEED) != run(SEED + 1)


def test_invalid_settings_are_refused():
    """No parameter, bounds on another attribute or a non-positive sd is an error."""
    members = _members(SMALL)
    with pytest.raises(ValueError, match="at least one parameter"):
        EnsembleKalmanFilter(members, _theta(), sd=1.0, parameters=[])
    with pytest.raises(ValueError, match="bounds"):
        EnsembleKalmanFilter(
            members, _theta(), sd=1.0, parameters=["theta"], bounds={"x": (0, 1)}
        )
    enkf = EnsembleKalmanFilter(
        members, _theta(), sd={"level": 0.0}, parameters=["theta"]
    )
    with pytest.raises(ValueError, match="positive"):
        enkf.assimilate(Observation(1.0, {"level": 1.0}))
