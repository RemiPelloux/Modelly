"""Equations inside agents, as the paper quotes them: data/odes.json.

    python paper/scripts/odes.py

Four checks, each the measurement a test in ``tests/couple`` asserts on, recorded with its
value: ``solve_batch`` against one ``solve_ivp`` call per system (200 random viral systems,
two methods, two tolerances: how many systems take exactly ``solve_ivp``'s accepted steps,
and the largest relative difference of the final states); the delay equation
``y' = -a y(t - 1)`` against its closed form at three model steps; the strong orders of the
two SDE schemes on geometric Brownian motion; and the exponent of the gap between the Bass
zoo model and its mean-field limit over population sizes. With JAX installed, also the
differentiable ODE phase: the viral rates recovered by gradient calibration and the gradient
check against finite differences (``tests/diff/test_ode.py``).
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

import numpy as np
from environment import environment
from scipy.integrate import solve_ivp

PAPER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PAPER.parent))

from modelly.couple.agent_ode import AgentODE  # noqa: E402
from modelly.couple.batch import solve_batch  # noqa: E402
from modelly.couple.delay import Delay  # noqa: E402
from modelly.couple.meanfield import gap_by_size  # noqa: E402
from tests.couple import test_batch, test_delay, test_meanfield, test_sde  # noqa: E402

SIZES = [250, 1000, 4000, 16000]
TOLERANCES = [(1e-3, 1e-6), (1e-8, 1e-10)]


def population() -> tuple[dict, np.ndarray]:
    """The test's 200 random viral systems (the ``population`` fixture of test_batch.py)."""
    rng, n = np.random.default_rng(7), test_batch.SYSTEMS
    params = {
        "r": rng.uniform(0.5, 2.0, n),
        "c": rng.uniform(0.5, 1.5, n),
        "a": rng.uniform(0.1, 1.0, n),
        "d": 0.3,
    }
    return params, np.vstack([rng.uniform(0.01, 1.0, n), np.zeros(n)])


def reference(
    params: dict, y0: np.ndarray, j: int, method: str, rtol: float, atol: float
):
    """System ``j`` solved alone by solve_ivp."""
    return solve_ivp(
        test_batch.viral,
        (0.0, 10.0),
        y0,
        method=method,
        rtol=rtol,
        atol=atol,
        args=(test_batch.one(params, j),),
    )


def compare_one(
    params: dict, y0: np.ndarray, method: str, rtol: float, atol: float
) -> dict:
    """One method and tolerance: systems with solve_ivp's step count, largest difference."""
    batch = solve_batch(
        test_batch.viral, (0.0, 10.0), y0, params, method=method, rtol=rtol, atol=atol
    )
    same, worst = 0, 0.0
    for j in range(test_batch.SYSTEMS):
        ref = reference(params, y0[:, j], j, method, rtol, atol)
        same += int(batch.nsteps[j] == ref.t.size - 1)
        scale = np.maximum(np.abs(ref.y[:, -1]), atol)
        worst = max(worst, float((np.abs(batch.y[:, j] - ref.y[:, -1]) / scale).max()))
    return {
        "method": method,
        "rtol": rtol,
        "atol": atol,
        "systems": test_batch.SYSTEMS,
        "same_steps": same,
        "max_relative_difference": worst,
    }


def batch_against_solve_ivp() -> list[dict]:
    """Every method and tolerance of the test, compared system by system."""
    params, y0 = population()
    return [
        compare_one(params, y0, method, rtol, atol)
        for method in ("RK45", "RK23")
        for rtol, atol in TOLERANCES
    ]


def delay_against_closed_form() -> list[dict]:
    """The largest relative error at t = 3 for model steps of 1, 0.5 and 3."""
    rows = []
    for step in (1.0, 0.5, 3.0):
        model = test_delay.cells()
        ode = AgentODE(
            model,
            test_delay.Cell,
            test_delay.lagged,
            ["y"],
            ["rate"],
            solver=test_delay.TIGHT,
            delays={"past": Delay("y", 1.0, before=1.0)},
        )
        for start in np.arange(0.0, 3.0, step):
            ode.advance(start, step)
        exact = test_delay.exact(test_delay.RATES, 3.0)
        error = np.abs(model.columns[test_delay.Cell].y - exact) / np.abs(exact)
        rows.append({"step": step, "max_relative_error": float(error.max())})
    return rows


def sde_orders() -> dict[str, float]:
    """The fitted strong order of each scheme."""
    steps = test_sde.T * np.array(test_sde.FACTORS) / test_sde.FINE
    return {
        scheme: float(
            np.polyfit(np.log(steps), np.log(test_sde.strong_errors(scheme)), 1)[0]
        )
        for scheme in ("euler", "milstein")
    }


def observed_load(t) -> list[float]:
    """The mean log viral load each day under the true rates, as test_ode.py observes it."""
    y = np.vstack([np.ones(t.HOSTS), np.zeros(t.HOSTS), t.DOSES])
    observed = [np.log(y[2]).mean()]
    for day in range(t.DAYS):
        y = solve_batch(t.tiv, (day, day + 1.0), y, t.TRUTH, rtol=1e-9, atol=1e-12).y
        observed.append(np.log(y[2]).mean())
    return observed


def gradient_recovery() -> dict:
    """The fitted viral rates' relative errors and the gradient check, as test_ode.py runs them."""
    from modelly.calibrate import Prior, Target  # noqa: PLC0415 (JAX is optional)
    from modelly.diff import GradientCalibration, GradientOptions, check_gradients  # noqa: PLC0415 (JAX is optional)
    from tests.diff import test_ode as t  # noqa: PLC0415 (JAX is optional)

    priors = {
        "beta": Prior.log_uniform(2.0, 40.0),
        "clearance": Prior.log_uniform(1.0, 9.0),
    }
    options = GradientOptions(steps=t.DAYS, iterations=200, learning_rate=0.05, seed=0)
    fit = GradientCalibration(
        t.MODEL, priors, [Target("load", observed=observed_load(t))], options
    ).run()
    check = check_gradients(
        lambda p: t.MODEL.simulate(p, t.DAYS, seed=0)["load"][-1], t.TRUTH
    )
    errors = {k: abs(float(fit.params[k]) - v) / v for k, v in t.TRUTH.items()}
    return {
        "relative_errors": errors,
        "gradient_check_ok": bool(check.ok),
        "gradient_relative_error": {
            k: float(v) for k, v in check.relative_error.items()
        },
    }


def main() -> None:
    """Run the four checks and write data/odes.json."""
    gap = gap_by_size(test_meanfield.run, SIZES, seeds=[1, 2, 3])
    out = {
        "environment": environment(),
        "batch_against_solve_ivp": batch_against_solve_ivp(),
        "delay_against_closed_form": delay_against_closed_form(),
        "sde_strong_orders": sde_orders() | {"paths": test_sde.PATHS},
        "mean_field_gap": {
            "sizes": SIZES,
            "gaps": [float(g) for g in gap.gaps],
            "exponent": float(gap.exponent),
        },
    }
    with contextlib.suppress(ImportError):  # no JAX: the gradient study is left out
        out["gradient_recovery"] = gradient_recovery()
    (PAPER / "data" / "odes.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "environment"}, indent=1))


if __name__ == "__main__":
    main()
