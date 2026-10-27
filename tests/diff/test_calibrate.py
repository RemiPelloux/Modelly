"""GradientCalibration recovers known parameters of two zoo models, deterministically."""

import numpy as np
import pytest

jax = pytest.importorskip("jax")

from modelly.calibrate import Prior, Target  # noqa: E402
from modelly.diff import GradientCalibration, GradientOptions  # noqa: E402
from modelly.zoo.bass_diffusion.differentiable import (  # noqa: E402
    differentiable_model as bass_model,
)
from modelly.zoo.bass_diffusion.model import BassDiffusion, BassScenario  # noqa: E402
from modelly.zoo.bouchaud_mezard.differentiable import (  # noqa: E402
    differentiable_model as wealth_model,
)
from modelly.zoo.bouchaud_mezard.model import (  # noqa: E402
    BouchaudMezard,
    BouchaudMezardScenario,
)

APPROXIMATE = "ignore::modelly.diff.GradientApproximationWarning"
BASS_TRUTH = {"innovation": 0.03, "imitation": 0.38}
WEALTH_TRUTH = {"volatility": 1.5, "exchange": 1.0}


def bass_observed(households, steps):
    """The adoption curve of the agent-based zoo model at the true parameters."""
    zoo = BassDiffusion(
        BassScenario(rng=7, households=households, steps=steps, **BASS_TRUTH)
    )
    zoo.run()
    return zoo.datacollector.get_model_vars_dataframe()["adoption"].to_numpy()


def bass_calibration(households=20_000, steps=100, iterations=150):
    """Fit innovation and imitation of the straight-through twin to the zoo curve."""
    priors = {
        "innovation": Prior.log_uniform(0.001, 0.3),
        "imitation": Prior.uniform(0.05, 1.0),
    }
    targets = [Target("adoption", observed=bass_observed(households, steps))]
    options = GradientOptions(
        steps=steps, iterations=iterations, learning_rate=0.05, seed=1
    )
    return GradientCalibration(
        bass_model(households=households), priors, targets, options
    )


@pytest.mark.filterwarnings(APPROXIMATE)
def test_bass_recovers_innovation_and_imitation():
    """From the prior medians (0.017, 0.525) to within 5% of (0.03, 0.38)."""
    fit = bass_calibration().run()
    for name, truth in BASS_TRUTH.items():
        assert abs(fit.params[name] / truth - 1) < 0.05, fit.params
    assert fit.loss < fit.history["loss"].iloc[0] / 10
    assert set(fit.gradient) == set(BASS_TRUTH)


def test_bouchaud_mezard_recovers_volatility_and_exchange():
    """From the prior medians (1, 1) to within 10% of (1.5, 1.0), exact pathwise gradients."""
    n, steps, replicates = 1000, 300, 2
    runs = []
    for seed in range(replicates):
        scenario = BouchaudMezardScenario(
            rng=7 + seed, n=n, steps=steps, **WEALTH_TRUTH
        )
        zoo = BouchaudMezard(scenario)
        zoo.run()
        runs.append(zoo.datacollector.get_model_vars_dataframe()["gini"].to_numpy())
    calibration = GradientCalibration(
        wealth_model(n=n),
        {
            "volatility": Prior.log_uniform(0.2, 5.0),
            "exchange": Prior.log_uniform(0.1, 10.0),
        },
        [Target("gini", observed=np.mean(runs, axis=0))],
        GradientOptions(
            steps=steps,
            iterations=120,
            learning_rate=0.05,
            seed=1,
            replicates=replicates,
        ),
    )
    fit = calibration.run()
    for name, truth in WEALTH_TRUTH.items():
        assert abs(fit.params[name] / truth - 1) < 0.10, fit.params


@pytest.mark.filterwarnings(APPROXIMATE)
def test_same_seed_same_fit():
    """Common random numbers and a fixed seed: two runs give the same history."""
    first = bass_calibration(households=2000, steps=40, iterations=15).run()
    second = bass_calibration(households=2000, steps=40, iterations=15).run()
    assert first.history.equals(second.history) and first.params == second.params


def test_summaries_and_distances():
    """A summary target and the built-in distances are traced in JAX."""
    model = wealth_model(n=100)
    target = Target(
        "gini", observed=[0.1], summary=lambda series: series[-1], distance="mae"
    )
    calibration = GradientCalibration(
        model,
        {"volatility": Prior.uniform(0.5, 2.0)},
        [target],
        GradientOptions(steps=20, iterations=3, fixed={"exchange": 1.0}),
    )
    value = calibration.loss({"volatility": 1.0, "exchange": 1.0})
    assert np.isfinite(float(value))
    fit = calibration.run()
    assert list(fit.params) == ["volatility"] and len(fit.history) == 3


def test_definition_errors():
    """Missing priors, targets or outputs, and too-long series, are refused."""
    model = wealth_model(n=50)
    priors = {"volatility": Prior.uniform(0.5, 2.0)}
    with pytest.raises(ValueError):
        GradientCalibration(model, {}, [Target("gini", observed=[0.1])])
    with pytest.raises(ValueError):
        GradientCalibration(model, priors, [Target("wealth", observed=[0.1])])
    with pytest.raises(ValueError):
        GradientCalibration(
            model,
            priors,
            [Target("gini", observed=np.zeros(50))],
            GradientOptions(steps=10),
        )
