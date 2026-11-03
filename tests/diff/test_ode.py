"""ODE parameters by gradient: autodiff against finite differences, and a calibration."""

import numpy as np
import pytest

jax = pytest.importorskip("jax")

from modelly.calibrate import Prior, Target  # noqa: E402
from modelly.couple.batch import solve_batch  # noqa: E402
from modelly.diff import (  # noqa: E402
    DiffModel,
    GradientCalibration,
    GradientOptions,
    check_gradients,
)
from modelly.diff._jax import jnp  # noqa: E402
from modelly.diff.ode import integrate, ode_phase  # noqa: E402

HOSTS, DAYS = 20, 8
TRUTH = {"beta": 10.0, "clearance": 3.0}
DOSES = np.geomspace(1e-5, 1e-2, HOSTS)


def tiv(t, y, p):
    """The target-cell-limited model, written with ``jax.numpy`` (and numpy-compatible)."""
    cells, infected, virus = y
    infection = p["beta"] * cells * virus
    xp = jnp if isinstance(y, jax.Array) else np
    return xp.stack(
        [
            -infection,
            infection - 2.0 * infected,
            20.0 * infected - p["clearance"] * virus,
        ]
    )


def init(params, rng):
    """Every host with all its cells and its own dose."""
    return {
        "cells": jnp.ones(HOSTS),
        "infected": jnp.zeros(HOSTS),
        "virus": jnp.asarray(DOSES),
    }


def mean_load(state, params):
    """The mean log virus load over the hosts."""
    return jnp.log(state["virus"]).mean()


MODEL = DiffModel(
    init, [ode_phase(tiv, ["cells", "infected", "virus"])], {"load": mean_load}
)


def test_integrate_agrees_with_solve_batch():
    """RK4 on 256 steps and solve_batch reach the same state; halving the step converges."""
    y0 = np.vstack([np.ones(HOSTS), np.zeros(HOSTS), DOSES])
    ref = solve_batch(tiv, (0.0, 2.0), y0, TRUTH, rtol=1e-11, atol=1e-14).y
    with jax.enable_x64(True):
        errors = [
            np.abs(
                np.asarray(integrate(tiv, jnp.asarray(y0), 2.0, TRUTH, n)) - ref
            ).max()
            for n in (64, 128, 256)
        ]
    assert errors[-1] < 2e-6
    assert errors[0] / errors[1] == pytest.approx(16, rel=0.25)  # fourth order


def test_gradients_match_finite_differences():
    """D (load after eight days) / d (beta, clearance), by the adjoint and by differences."""

    def final_load(params):
        return MODEL.simulate(params, DAYS, seed=0)["load"][-1]

    check = check_gradients(final_load, TRUTH)
    assert check.ok, check.relative_error


def test_gradient_calibration_recovers_the_viral_parameters():
    """From the prior medians to within 2% of the truth, on the loads solve_batch computes."""
    y = np.vstack([np.ones(HOSTS), np.zeros(HOSTS), DOSES])
    observed = [np.log(y[2]).mean()]
    for day in range(DAYS):
        y = solve_batch(tiv, (day, day + 1.0), y, TRUTH, rtol=1e-9, atol=1e-12).y
        observed.append(np.log(y[2]).mean())
    priors = {
        "beta": Prior.log_uniform(2.0, 40.0),
        "clearance": Prior.log_uniform(1.0, 9.0),
    }
    options = GradientOptions(steps=DAYS, iterations=200, learning_rate=0.05, seed=0)
    fit = GradientCalibration(
        MODEL, priors, [Target("load", observed=observed)], options
    ).run()
    for name, truth in TRUTH.items():
        assert fit.params[name] == pytest.approx(truth, rel=0.02), fit.params
