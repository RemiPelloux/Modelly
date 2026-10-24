"""Tests for ABC rejection, simulated moments and Bayesian optimisation."""

import numpy as np
import pytest

from modelly.calibrate import (
    ABCRejection,
    BayesOpt,
    CalibrationError,
    Prior,
    SimulatedMoments,
    Target,
)
from modelly.calibrate.gp import GaussianProcess, expected_improvement
from modelly.calibrate.optimize import UnitBox
from tests.calibrate.models import Noisy, mean_and_sd
from tests.calibrate.shared import SIR_TRUTH, STEPS, sir_priors, sir_targets

pytest.importorskip("pyarrow")

MOMENT_STEPS = 20
TRUE_MOMENTS = [1.5, 0.5]


def noisy_targets():
    """The mean and sd of the Noisy model's series."""
    return [Target("value", TRUE_MOMENTS, summary=mean_and_sd, distance="euclidean")]


def noisy_priors():
    """Priors over the Noisy model's mean and scale."""
    return {"mean": Prior.uniform(-3.0, 3.0), "scale": Prior.log_uniform(0.1, 3.0)}


def test_rejection_keeps_the_closest():
    """The quantile keeps the closest samples; a tolerance keeps those within it."""
    calibration = ABCRejection(
        "tests.calibrate.models:SIR", sir_priors(), sir_targets(), steps=STEPS, seed=2
    )
    posterior = calibration.run(budget=200, quantile=0.1)
    assert len(posterior) == 20 and posterior.info["acceptance"] == 0.1
    assert abs(posterior.summary().loc["beta", "mean"] - SIR_TRUTH["beta"]) < 0.15
    within = calibration.run(budget=200, tolerance=posterior.info["tolerance"])
    assert len(within) == 20
    with pytest.raises(CalibrationError):
        calibration.run(budget=10, tolerance=0.0)
    with pytest.raises(ValueError):
        calibration.run(budget=10, quantile=None)


def test_simulated_moments_recovers_mean_and_scale():
    """Nelder-Mead and Powell over common random numbers find both moments."""
    for optimizer, weighting in (("Nelder-Mead", "identity"), ("Powell", "diagonal")):
        fit = SimulatedMoments(
            Noisy, noisy_priors(), noisy_targets(), steps=MOMENT_STEPS, replicates=4,
            seed=3, weighting=weighting, optimizer=optimizer,
        )  # fmt: skip
        best = fit.run(evaluations=120).best
        assert best["mean"] == pytest.approx(TRUE_MOMENTS[0], abs=0.3)
        assert best["scale"] == pytest.approx(TRUE_MOMENTS[1], abs=0.2)
        assert len(fit.trace()) <= 130


def test_simulated_moments_settings():
    """Weighting matrices are checked; choices and one replicate are refused where needed."""
    priors, targets = noisy_priors(), noisy_targets()
    with pytest.raises(ValueError):
        SimulatedMoments(Noisy, priors, targets, weighting="optimal")
    with pytest.raises(ValueError):
        SimulatedMoments(Noisy, priors, targets, optimizer="BFGS")
    with pytest.raises(TypeError):
        SimulatedMoments(Noisy, {"mean": Prior.choice([0, 1])}, targets)
    fit = SimulatedMoments(Noisy, priors, targets, steps=5, weighting=np.eye(3))
    with pytest.raises(ValueError):
        fit.run(evaluations=2)
    optimal = SimulatedMoments(
        Noisy, priors, targets, steps=5, replicates=3, weighting="optimal"
    )
    assert optimal.run(evaluations=5).info["evaluations"] >= 1


def test_bayes_opt_finds_the_mean():
    """The Gaussian-process search gets close to the true mean."""
    targets = [Target("value", [1.5], summary=np.mean)]
    priors = {"mean": Prior.uniform(-3.0, 3.0)}
    search = BayesOpt(Noisy, priors, targets, steps=MOMENT_STEPS, replicates=2, seed=1)
    posterior = search.run(evaluations=14, initial=6)
    assert posterior.best["mean"] == pytest.approx(1.5, abs=0.3)
    assert len(search.trace()) == 14
    again = BayesOpt(Noisy, priors, targets, steps=MOMENT_STEPS, replicates=2, seed=1)
    assert again.run(evaluations=14, initial=6).best == posterior.best
    with pytest.raises(ValueError):
        search.run(evaluations=3, initial=5)


def test_unit_box_round_trip():
    """Log-scaled priors map on a log scale; the map inverts."""
    box = UnitBox({"a": Prior.uniform(0.0, 2.0), "b": Prior.log_uniform(0.01, 1.0)})
    params = box.params([0.5, 0.5])
    assert params["a"] == 1.0 and params["b"] == pytest.approx(0.1)
    np.testing.assert_allclose(box.unit(params), [0.5, 0.5])


def test_gaussian_process_interpolates():
    """The process fits a smooth function and is unsure far from the data."""
    x = np.linspace(0, 1, 10)[:, None]
    process = GaussianProcess.fit(x, np.sin(6 * x[:, 0]))
    mean, sd = process.predict(np.array([[0.55], [0.0]]))
    assert mean[0] == pytest.approx(np.sin(3.3), abs=0.05)
    gain = expected_improvement(np.array([0.0, 1.0]), np.array([0.1, 0.1]), 0.5)
    assert gain[0] > gain[1] >= 0
    assert sd[1] < 0.2
