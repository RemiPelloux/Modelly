"""Active learning against Latin hypercubes: how many runs reach the same emulator accuracy.

    python benchmarks/emulate/active_vs_lhs.py branin --criterion ivr --runs 80
    python benchmarks/emulate/active_vs_lhs.py ishigami --runs 100
    python benchmarks/emulate/active_vs_lhs.py bass --runs 60

The protocol of ``tests/emulate/test_active.py``: accuracy is the normalised RMSE of a
Gaussian-process emulator on random test points (for the zoo model, test runs with the
same common random numbers as the training runs); a Latin hypercube of ``n`` runs scores
the median over three seeds; active learning starts from its own hypercube of
``2 d + 2`` runs and adds ``--batch`` runs at a time. For every ten active runs the
script prints the error, the hypercube runs needed for that error (interpolated on a log
scale between the sizes measured) and their ratio, the factor saved.

Small matrices are slow with a multi-threaded BLAS on a busy machine: run it with
``OPENBLAS_NUM_THREADS=1``.
"""

from __future__ import annotations

import argparse
import math
from itertools import pairwise

import numpy as np
from scipy.stats import qmc

from modelly.emulate import ActiveLearning, ActiveSettings, GaussianEmulator, Simulation
from modelly.experiments import ScenarioSpace
from modelly.zoo.bass_diffusion.model import BassDiffusion

PI = math.pi
LHS_SEEDS = (1, 2, 3)
TEST_POINTS = 500
TEST_SEED = 12345
STEP = 10
HOUSEHOLDS = 20_000
BASS_STEPS = 40  # four years at the default dt of 0.1


def branin(x1, x2):
    """The Branin function on [-5, 10] x [0, 15]."""
    b, c, t = 5.1 / (4 * PI**2), 5 / PI, 1 / (8 * PI)
    return (x2 - b * x1**2 + c * x1 - 6) ** 2 + 10 * (1 - t) * math.cos(x1) + 10


def ishigami(x1, x2, x3):
    """The Ishigami function on [-pi, pi]^3 (a = 7, b = 0.1)."""
    return math.sin(x1) + 7 * math.sin(x2) ** 2 + 0.1 * x3**4 * math.sin(x1)


def simulation(case: str) -> Simulation:
    """The benchmark's simulation: two analytic functions and a zoo model."""
    if case == "branin":
        return Simulation(
            branin, ScenarioSpace(x1=(-5.0, 10.0), x2=(0.0, 15.0)), seed=1
        )
    if case == "ishigami":
        cube = ScenarioSpace(x1=(-PI, PI), x2=(-PI, PI), x3=(-PI, PI))
        return Simulation(ishigami, cube, seed=1)
    space = ScenarioSpace(
        innovation=(0.005, 0.05), imitation=(0.1, 0.8), households=HOUSEHOLDS
    )
    return Simulation(
        BassDiffusion, space, ["adoption"], steps=BASS_STEPS, common=True, seed=1
    )


def error(units, values, test) -> float:
    """The normalised RMSE on ``test`` of an emulator fitted to ``units`` and ``values``."""
    return next(iter(GaussianEmulator.fit(units, values).score(*test).values()))


def lhs_curve(sim: Simulation, sizes, test) -> dict[int, float]:
    """The median error of Latin hypercubes of each size."""
    curve = {}
    for size in sizes:
        errors = []
        for seed in LHS_SEEDS:
            rng = np.random.default_rng(seed)
            units = qmc.LatinHypercube(len(sim.space.dimensions), rng=rng).random(size)
            errors.append(error(units, sim.evaluate(units, (1, seed, size)), test))
        curve[size] = float(np.median(errors))
    return curve


def needed(curve: dict[int, float], target: float) -> float:
    """The hypercube runs that reach ``target``, interpolated on a log scale."""
    sizes = sorted(curve)
    for low, high in pairwise(sizes):
        if curve[high] <= target:
            if curve[low] <= target:
                return float(low)
            a, b = math.log(curve[low]), math.log(curve[high])
            return low + (high - low) * (a - math.log(target)) / (a - b)
    return math.inf


def main() -> None:
    """Print the active-learning errors and the factor of runs they save."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("case", choices=["branin", "ishigami", "bass"])
    parser.add_argument("--criterion", default="ivr", choices=["ivr", "variance"])
    parser.add_argument("--runs", type=int, default=60)
    parser.add_argument("--batch", type=int, default=4)
    args = parser.parse_args()
    sim = simulation(args.case)
    units = np.random.default_rng(TEST_SEED).random(
        (TEST_POINTS, len(sim.space.dimensions))
    )
    test = (units, sim.evaluate(units, (2,)))
    curve = lhs_curve(sim, range(STEP, 2 * args.runs + 1, STEP), test)
    print("lhs", {size: round(value, 4) for size, value in curve.items()})
    settings = ActiveSettings(batch=args.batch, criterion=args.criterion)
    design = ActiveLearning(sim, settings).run(args.runs)
    first = 2 * (len(sim.space.dimensions) + 1)
    for runs in range(STEP, args.runs + 1, STEP):
        if runs >= first:
            value = error(design.units[:runs], design.values[:runs], test)
            lhs = needed(curve, value)
            print(
                f"{runs:4d} runs  error {value:.4f}  lhs {lhs:6.1f}  factor {lhs / runs:.2f}"
            )


if __name__ == "__main__":
    main()
