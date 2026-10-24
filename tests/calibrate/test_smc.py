"""Tests for ABC-SMC: parameter recovery, resume, stopping rules and determinism."""

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from modelly.calibrate import ABCSMC, CalibrationError, Prior, Target
from tests.calibrate.models import AgentSIR, SIRScenario
from tests.calibrate.shared import (
    PREY_TRUTH,
    SIR_TRUTH,
    prey_smc,
    recovered,
    sir_smc,
    sir_targets,
)

pytest.importorskip("pyarrow")

RELATIVE_ERROR = 0.25
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_recovers_sir_parameters(seed):
    """Posterior means within 25 % of the truth, which lies in the 95 % HDI."""
    posterior = sir_smc(seed, particles=30).run(generations=6)
    assert recovered(posterior, SIR_TRUTH, RELATIVE_ERROR), posterior.summary()


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_recovers_predator_prey_parameters(seed):
    """Both rates of the stochastic Lotka-Volterra model, from both series."""
    posterior = prey_smc(seed).run(generations=6)
    assert recovered(posterior, PREY_TRUTH, RELATIVE_ERROR), posterior.summary()


def test_generations_shrink_the_tolerance():
    """Tolerances decrease; weights are normalised; the trace has one row per generation."""
    calibration = sir_smc(particles=20)
    posterior = calibration.run(generations=3)
    trace = calibration.trace()
    assert list(trace["generation"]) == [0, 1, 2]
    assert trace["tolerance"].is_monotonic_decreasing
    assert posterior.weights.sum() == pytest.approx(1.0)
    assert 1 <= posterior.effective_sample_size <= 20
    assert posterior.info["runs"] == trace["runs"].sum()
    assert posterior.info["stopped"] == "generations"


def test_resume_gives_the_same_posterior(tmp_path):
    """Stopped after one generation (or by the budget), saved, loaded: same final posterior."""
    uninterrupted = sir_smc(particles=20)
    whole = uninterrupted.run(generations=3).to_dataframe()
    first = sir_smc(particles=20)
    first.run(generations=1)
    first.save(tmp_path / "calib.ckpt")
    resumed = ABCSMC.load(tmp_path / "calib.ckpt").run(generations=3)
    pd.testing.assert_frame_equal(resumed.to_dataframe(), whole)
    starved = sir_smc(particles=20)
    starved.run(budget=uninterrupted.runs - 1, generations=3)
    assert starved.stopped == "budget" and len(starved.history) == 2
    starved.save(tmp_path / "starved.ckpt")
    again = ABCSMC.load(tmp_path / "starved.ckpt").run(generations=3)
    pd.testing.assert_frame_equal(again.to_dataframe(), whole)


def test_checkpoint_option_saves_every_generation(tmp_path):
    """``checkpoint=`` writes a loadable file after each generation."""
    path = tmp_path / "progress.ckpt"
    sir_smc(particles=10).run(generations=2, checkpoint=path)
    assert len(ABCSMC.load(path).history) == 2


def test_store_is_reused(tmp_path):
    """A rerun into the same store reads the runs instead of running them again."""
    first = sir_smc(particles=10, store=tmp_path).run(generations=2)
    files = sorted(tmp_path.rglob("*.parquet"))
    second = sir_smc(particles=10, store=tmp_path).run(generations=2)
    assert sorted(tmp_path.rglob("*.parquet")) == files
    pd.testing.assert_frame_equal(first.to_dataframe(), second.to_dataframe())


def test_stopping_rules():
    """Minimum tolerance and acceptance stop the run; no generation at all is an error."""
    calibration = sir_smc(particles=10, min_tolerance=1e9)
    calibration.run(generations=5)
    # generation 1 reaches the minimum (generation 0 accepts everything)
    assert calibration.stopped == "min_tolerance" and len(calibration.history) == 2
    strict = sir_smc(particles=10, quantile=0.01, min_acceptance=0.5)
    strict.run(generations=5)
    assert strict.stopped == "min_acceptance"
    with pytest.raises(CalibrationError):
        sir_smc(particles=10).run(budget=5)


def test_choice_prior_is_calibrated():
    """A discrete parameter moves with the discrete kernel and stays in its values."""
    priors = {"beta": Prior.uniform(0.05, 1.0), "initial": Prior.choice([2, 10, 40])}
    fixed = {"gamma": SIR_TRUTH["gamma"]}
    calibration = ABCSMC(
        "tests.calibrate.models:SIR", priors, sir_targets(), steps=30, seed=4,
        particles=20, fixed=fixed,
    )  # fmt: skip
    posterior = calibration.run(generations=4)
    frame = posterior.to_dataframe()
    assert set(frame["initial"]) <= {2, 10, 40}
    shares = frame.groupby("initial")["weight"].sum()
    assert shares.idxmax() == SIRScenario.initial


def test_definition_errors():
    """Unknown or mistyped parameters, clashing names and bad settings are refused."""
    targets = sir_targets()
    with pytest.raises(ValueError):
        ABCSMC(AgentSIR, {"nope": Prior.uniform(0, 1)}, targets)
    with pytest.raises(TypeError):
        ABCSMC(AgentSIR, {"population": Prior.uniform(0, 1)}, targets)
    with pytest.raises(ValueError):
        ABCSMC(AgentSIR, {"infected": Prior.uniform(0, 1)}, [Target("infected", [1.0])])
    with pytest.raises(ValueError):
        ABCSMC(AgentSIR, {}, targets)
    with pytest.raises(ValueError):
        sir_smc(particles=0)


def test_lambda_cannot_be_saved(tmp_path):
    """A lambda summary makes the checkpoint fail with a clear error."""
    target = Target("infected", [1.0], summary=lambda series: series.max())
    calibration = ABCSMC(AgentSIR, {"beta": Prior.uniform(0.1, 1.0)}, [target])
    with pytest.raises(CalibrationError, match="module-level"):
        calibration.save(tmp_path / "x.ckpt")


def test_not_a_checkpoint(tmp_path):
    """Loading another file is a CalibrationError."""
    path = tmp_path / "x.ckpt"
    path.write_bytes(b"hello\n")
    with pytest.raises(CalibrationError):
        ABCSMC.load(path)


def agent_smc(executor):
    """A tiny calibration of the agent-based SIR; its posterior as a DataFrame."""
    target = Target("infected", [3.0, 5.0, 6.0, 7.0])
    calibration = ABCSMC(
        AgentSIR, {"beta": Prior.uniform(0.1, 1.5)}, [target], steps=6, seed=8,
        particles=8,
    )  # fmt: skip
    return calibration.run(
        generations=2, executor=executor, max_parallel=2
    ).to_dataframe()


def test_same_posterior_on_every_executor():
    """Serial, threads and processes give the identical posterior."""
    serial = agent_smc("serial")
    pd.testing.assert_frame_equal(agent_smc("threads"), serial)
    pd.testing.assert_frame_equal(agent_smc("processes"), serial)


def test_same_posterior_with_the_pure_python_core(tmp_path):
    """MODELLY_PURE_PYTHON=1 in a fresh process gives the posterior of this process."""
    out = tmp_path / "pure.csv"
    code = (
        "import sys; from tests.calibrate.test_smc import agent_smc; "
        "agent_smc('serial').to_csv(sys.argv[1], index=False)"
    )
    env = {**os.environ, "MODELLY_PURE_PYTHON": "1", "PYTHONPATH": str(ROOT)}
    subprocess.run(
        [sys.executable, "-c", code, str(out)], check=True, env=env, cwd=ROOT
    )
    compiled = agent_smc("serial")
    pure = pd.read_csv(out, float_precision="round_trip")
    pd.testing.assert_frame_equal(pure, compiled, check_exact=True)
