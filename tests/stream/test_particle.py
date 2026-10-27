"""Tests for the particle filter: resampling, weights, reproducibility (modelly.stream.particle)."""

import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from stream_support import (
    DAYS,
    NOISE,
    cases,
    ensemble,
    filtered,
    fingerprint,
    observations,
)

from modelly.stream import FilterStep, Observation, ObservationOperator, ParticleFilter
from modelly.stream.particle import effective_sample_size, systematic_resample

REPO = Path(__file__).resolve().parents[2]

# Runs the filter in a fresh interpreter and prints the core it used and the digest.
DIGEST = """
import sys
sys.path.insert(0, sys.argv[1])
from stream_support import filtered, fingerprint
from modelly.core import rng
print(rng.NATIVE, fingerprint(filtered()))
"""


def test_systematic_resampling_follows_the_cumulative_weights():
    """Slot k takes the replicate whose cumulative weight passes (u + k) / n."""
    weights = [0.1, 0.2, 0.3, 0.4]
    assert systematic_resample(weights, 0.5).tolist() == [1, 2, 3, 3]
    assert systematic_resample(weights, 0.0).tolist() == [0, 1, 2, 3]
    assert systematic_resample([0, 0, 1, 0], 0.99).tolist() == [2, 2, 2, 2]


def test_systematic_resampling_keeps_counts_within_one_of_n_w():
    """Each replicate is drawn floor(n w) or ceil(n w) times (Douc & Cappé 2005)."""
    rng = np.random.default_rng(3)
    weights = rng.random(50)
    expected = 50 * weights / weights.sum()
    for _ in range(20):
        counts = np.bincount(systematic_resample(weights, rng.random()), minlength=50)
        assert np.all(counts >= np.floor(expected)) and np.all(
            counts <= np.ceil(expected)
        )


def test_systematic_resampling_refuses_a_uniform_outside_the_unit_interval():
    """The uniform must be in [0, 1)."""
    with pytest.raises(ValueError, match="uniform"):
        systematic_resample([1, 1], 1.0)


def test_effective_sample_size_runs_from_one_to_n():
    """Equal weights give n; one replicate holding all the weight gives 1."""
    assert effective_sample_size([2, 2, 2, 2]) == pytest.approx(4)
    assert effective_sample_size([0, 0, 5, 0]) == pytest.approx(1)


def test_weights_follow_the_likelihood_without_resampling():
    """Below the threshold nothing resamples; the weights are the normalised likelihoods."""
    pf = ParticleFilter(ensemble(), cases(), sd=NOISE, threshold=1e-9)
    observation = Observation(1.0, {"cases": 3.0})
    step = pf.assimilate(observation)
    likelihood = np.array(
        [pf.operator.log_likelihood(m, observation, NOISE) for m in pf.ensemble]
    )
    expected = np.exp(likelihood - likelihood.max())
    np.testing.assert_allclose(pf.weights, expected / expected.sum())
    assert not step.resampled and pf.resamplings == 0
    assert step.ess == pytest.approx(pf.ess)
    mean = math.log(np.mean(np.exp(likelihood)))
    assert step.log_evidence == pytest.approx(mean)


def test_a_low_ess_resamples_and_resets_the_weights():
    """Threshold 1 resamples at every uneven step; weights are equal afterwards."""
    pf = filtered()
    assert pf.resamplings == pf.history["resampled"].sum() > 0
    np.testing.assert_array_equal(pf.weights, np.full(len(pf.ensemble), 1 / 12))
    assert list(pf.history.columns) == ["time", "ess", "resampled", "log_evidence"]
    assert len(pf.history) == DAYS


def test_estimate_is_the_weighted_mean():
    """The estimate weights each replicate's reading by its weight."""
    pf = ParticleFilter(ensemble(), cases(), sd=NOISE, threshold=1e-9)
    pf.assimilate(Observation(2.0, {"cases": 4.0}))
    readings = [m.new_cases for m in pf.ensemble]
    assert pf.estimate()["cases"] == pytest.approx(np.dot(pf.weights, readings))


def test_band_and_forecast_use_the_weights():
    """The band's mean is the weighted mean; the forecast leaves the ensemble in place."""
    pf = ParticleFilter(ensemble(), cases(), sd=NOISE, threshold=1e-9)
    pf.assimilate(Observation(2.0, {"cases": 4.0}))
    band = pf.band()
    assert band.loc[0, "mean"] == pytest.approx(pf.estimate()["cases"])
    ahead = pf.forecast(5.0, every=1.5)
    assert ahead["time"].tolist() == [2.0, 3.5, 5.0]
    assert pf.ensemble.time == 2.0


def test_run_returns_one_step_per_observation_up_to_until():
    """``run`` takes a source or a list, and stops at ``until``."""
    pf = ParticleFilter(ensemble(), cases(), sd=NOISE)
    records = [Observation(r["time"], {"cases": r["cases"]}) for r in observations()]
    steps = pf.run(records, until=5)
    assert [s.time for s in steps] == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert all(isinstance(s, FilterStep) for s in steps)


def test_zero_likelihood_everywhere_is_an_error():
    """A reading every replicate fails (NaN) leaves no weight to normalise."""
    broken = ObservationOperator(cases=lambda m: float("nan"))
    pf = ParticleFilter(ensemble(), broken, sd=NOISE)
    with pytest.raises(ValueError, match="zero likelihood"):
        pf.assimilate(Observation(1.0, {"cases": 1.0}))


def test_an_unreadable_replicate_gets_no_weight():
    """A NaN reading on one replicate gives it weight zero, not a NaN filter."""
    members = ensemble()
    odd = members[3]
    partial = ObservationOperator(
        cases=lambda m: float("nan") if m is odd else m.new_cases
    )
    pf = ParticleFilter(members, partial, sd=NOISE, threshold=1e-9)
    pf.assimilate(Observation(1.0, {"cases": 1.0}))
    assert pf.weights[3] == 0.0
    assert pf.weights.sum() == pytest.approx(1.0)


def test_threshold_must_be_a_fraction():
    """The ESS threshold is a fraction of the ensemble size in (0, 1]."""
    with pytest.raises(ValueError, match="threshold"):
        ParticleFilter(ensemble(), cases(), sd=NOISE, threshold=0)


def test_resampling_is_bit_identical_for_a_seed():
    """Two runs from the same seed agree bit for bit; another seed differs."""
    assert fingerprint(filtered()) == fingerprint(filtered())
    assert fingerprint(filtered()) != fingerprint(filtered(seed=7))


def test_duplicates_diverge_after_resampling():
    """Copies of one replicate are reseeded, so their generators differ."""
    pf = filtered()
    states = [m.random.getstate() for m in pf.ensemble]
    assert len(set(states)) == len(states)


@pytest.mark.parametrize("pure", [True, False])
def test_resampling_is_bit_identical_with_either_core(pure):
    """A fresh interpreter, compiled or pure-Python core, gives this process's run."""
    env = dict(os.environ)
    env.pop("MODELLY_PURE_PYTHON", None)
    if pure:
        env["MODELLY_PURE_PYTHON"] = "1"
    here = str(Path(__file__).parent)
    out = subprocess.run(
        [sys.executable, "-c", DIGEST, here],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    if not pure and out[0] == "False":
        pytest.skip("the compiled core is not built")
    assert out == [str(not pure), fingerprint(filtered())]
