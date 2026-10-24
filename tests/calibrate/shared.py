"""Helpers for the calibration tests: synthetic data and standard calibrations."""

import numpy as np

from modelly.calibrate import ABCSMC, Prior, Target
from modelly.profile.loader import build_model
from tests.calibrate.models import SIR, PreyPredator, log_counts

STEPS = 30
DATA_SEED = 99
SIR_TRUTH = {"beta": 0.4, "gamma": 0.1}
PREY_TRUTH = {"growth": 0.5, "predation": 0.01}


def synthetic(model, params, outputs, steps=STEPS, seed=DATA_SEED):
    """One run's series of ``outputs`` after steps 1..steps (the 'observed' data)."""
    instance = build_model(model, dict(params), np.random.SeedSequence(seed))
    series = {name: [] for name in outputs}
    for _ in range(steps):
        instance.step()
        for name in outputs:
            series[name].append(float(getattr(instance, name)))
    return {name: np.array(values) for name, values in series.items()}


def sir_targets():
    """The infected series of a SIR run at the true parameters."""
    observed = synthetic(SIR, SIR_TRUTH, ["infected"])
    return [Target("infected", observed["infected"])]


def sir_priors():
    """Uniform priors around the true SIR parameters."""
    return {"beta": Prior.uniform(0.05, 1.0), "gamma": Prior.uniform(0.02, 0.5)}


def sir_smc(seed=1, **settings):
    """A small ABC-SMC on the SIR model."""
    options = {"steps": STEPS, "seed": seed, "particles": 40} | settings
    return ABCSMC(SIR, sir_priors(), sir_targets(), **options)


def prey_smc(seed=1, **settings):
    """A small ABC-SMC on the predator-prey model, fitted to both series."""
    observed = synthetic(PreyPredator, PREY_TRUTH, ["prey", "predators"])
    targets = [
        Target(name, np.log1p(values), summary=log_counts)
        for name, values in observed.items()
    ]
    priors = {
        "growth": Prior.uniform(0.2, 1.0),
        "predation": Prior.log_uniform(0.002, 0.05),
    }
    options = {"steps": STEPS, "seed": seed, "particles": 40} | settings
    return ABCSMC(PreyPredator, priors, targets, **options)


def recovered(posterior, truth, relative):
    """Whether each posterior mean is within ``relative`` of the truth and inside the HDI."""
    summary = posterior.summary()
    for name, value in truth.items():
        row = summary.loc[name]
        if abs(row["mean"] - value) > relative * value:
            return False
        if not row["hdi_low"] <= value <= row["hdi_high"]:
            return False
    return True
