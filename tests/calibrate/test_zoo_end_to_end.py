"""A zoo model calibrated end to end: ABC-SMC recovers the Bass diffusion parameters.

The "observed" adoption curve is one run of ``modelly.zoo.bass_diffusion`` at the
default (true) parameters, innovation ``p = 0.03`` and imitation ``q = 0.38``.
ABC-SMC starts from wide uniform priors and, on every seed, the true values fall
inside the posterior's 95 % highest-density interval, which narrows by a factor of
several from the prior. This is the example of ``docs/calibration.md``, "A zoo model
end to end", at a smaller size.
"""

import numpy as np
import pytest

from modelly.calibrate import ABCSMC, Prior, Target
from modelly.zoo.bass_diffusion.model import BassDiffusion, BassScenario

pytest.importorskip("pyarrow")

TRUTH = {"innovation": 0.03, "imitation": 0.38}
PRIORS = {"innovation": (0.005, 0.1), "imitation": (0.05, 1.0)}
HOUSEHOLDS = 2000
STEPS = 80  # eight years in steps of 0.1
DATA_SEED = 99
SEEDS = (1, 2, 3)
PARTICLES = 60
GENERATIONS = 7
WORKERS = 4
NARROWING = 3  # the interval is at least this many times narrower than the prior


def observed_adoption() -> np.ndarray:
    """The adoption share after steps 0..STEPS of one run at the true parameters."""
    truth = BassDiffusion(BassScenario(rng=DATA_SEED, households=HOUSEHOLDS, **TRUTH))
    series = [truth.adoption]
    for _ in range(STEPS):
        truth.step()
        series.append(truth.adoption)
    return np.array(series)


@pytest.fixture(scope="module")
def adoption():
    """The observed curve, computed once."""
    return observed_adoption()


@pytest.mark.parametrize("seed", SEEDS)
def test_abc_smc_recovers_the_bass_parameters(adoption, seed):
    """Both true parameters lie in the 95 % HDI, much narrower than the prior."""
    calibration = ABCSMC(
        BassDiffusion,
        {name: Prior.uniform(*bounds) for name, bounds in PRIORS.items()},
        [Target("adoption", observed=adoption)],
        steps=STEPS,
        particles=PARTICLES,
        seed=seed,
        fixed={"households": HOUSEHOLDS},
    )
    posterior = calibration.run(
        generations=GENERATIONS, executor="processes", max_parallel=WORKERS
    )
    summary = posterior.summary()
    for name, true in TRUTH.items():
        low, high = summary.loc[name, ["hdi_low", "hdi_high"]]
        assert low <= true <= high, (name, low, high)
        prior_low, prior_high = PRIORS[name]
        assert (high - low) * NARROWING < prior_high - prior_low
