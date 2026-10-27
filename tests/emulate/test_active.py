"""Tests for active learning, and its benchmark against Latin hypercubes.

The benchmark protocol: an emulator is judged by its normalised RMSE on random
test points; a Latin hypercube of ``n`` runs scores the median over three
seeds; active learning starts from its own small hypercube and adds runs four
at a time. "Active learning matches a hypercube of ``m`` runs with ``n``" means
its error with ``n`` runs is at most the hypercube's with ``m``. The 1.4.0
roadmap asks for ``m = 2 n``; where that does not hold, the test pins the
factor measured instead (``benchmarks/emulate/active_vs_lhs.py`` prints the
whole curves).
"""

import math

import numpy as np
import pytest
from scipy.stats import qmc

from modelly.emulate import (
    ActiveLearning,
    ActiveSettings,
    GaussianEmulator,
    NeuralEmulator,
    NeuralSettings,
    Simulation,
)
from modelly.experiments import ScenarioSpace
from modelly.experiments.designs import Custom
from modelly.zoo.bass_diffusion.model import BassDiffusion
from tests.emulate.models import branin

BATCH = 4
LHS_SEEDS = (1, 2, 3)
TEST_POINTS = 500
TEST_SEED = 12345
BASS_HOUSEHOLDS = 10_000
BASS_STEPS = 40  # four years at the default dt of 0.1
BASS_TEST_RUNS = 200
BRANIN = ScenarioSpace(x1=(-5.0, 10.0), x2=(0.0, 15.0))
SQUARE = ScenarioSpace(x=(0.0, 1.0), y=(0.0, 1.0))


def wave(x, y):
    """A smooth function of the unit square."""
    return math.sin(6 * x) + y**2


def lhs_error(simulation, runs, test):
    """The median normalised RMSE of emulators fitted to Latin hypercubes of ``runs``."""
    errors = []
    for seed in LHS_SEEDS:
        rng = np.random.default_rng(seed)
        units = qmc.LatinHypercube(len(simulation.space.dimensions), rng=rng).random(
            runs
        )
        values = simulation.evaluate(units, (1, seed, runs))
        errors.append(GaussianEmulator.fit(units, values).score(*test)["y0"])
    return float(np.median(errors))


def active_error(simulation, runs, test):
    """The normalised RMSE of the emulator of an active-learning design of ``runs``."""
    design = ActiveLearning(simulation, ActiveSettings(batch=BATCH)).run(runs)
    return next(iter(design.emulator.score(*test).values()))


def test_same_seed_same_runs_and_resumable():
    """The same seed chooses the same runs, whether run at once or in two goes."""
    simulation = Simulation(wave, SQUARE, seed=3)
    settings = ActiveSettings(batch=2)
    whole = ActiveLearning(simulation, settings).run(14)
    split = ActiveLearning(simulation, settings)
    split.run(10)
    resumed = split.run(14)
    np.testing.assert_array_equal(whole.units, resumed.units)
    np.testing.assert_array_equal(whole.iterations, [0] * 6 + [1, 1, 2, 2, 3, 3, 4, 4])
    other = ActiveLearning(Simulation(wave, SQUARE, seed=4), settings).run(14)
    assert not np.array_equal(other.units, whole.units)


def smallest_gap(points):
    """The smallest distance between two of ``points``."""
    gaps = np.sqrt(((points[:, None] - points[None]) ** 2).sum(2))
    return gaps[np.triu_indices(len(points), 1)].min()


@pytest.mark.parametrize("criterion", ["ivr", "variance"])
def test_a_batch_spreads_out(criterion):
    """Conditioning on each pick keeps a batch further apart than the top scores are."""
    simulation = Simulation(wave, SQUARE, seed=1)
    learning = ActiveLearning(simulation, ActiveSettings(batch=6, criterion=criterion))
    design = learning.run(12)
    batch = design.units[design.iterations == 1]
    first = ActiveLearning(simulation, ActiveSettings(batch=6, criterion=criterion))
    first.run(6)
    candidates = first._stream(1).random((first.settings.candidates, 2))
    top = candidates[np.argsort(first._scores(first.fit(), candidates))[-6:]]
    assert len(batch) == 6
    assert smallest_gap(batch) > 2 * smallest_gap(top)


def test_design_as_rows_and_as_an_experiment_design():
    """The runs read back as a frame and as a custom design of their parameters."""
    simulation = Simulation(wave, SQUARE, seed=1)
    design = ActiveLearning(simulation, ActiveSettings(batch=2)).run(8)
    frame = design.frame()
    assert list(frame.columns) == ["iteration", "x", "y", "output"]
    np.testing.assert_allclose(
        frame["output"], [wave(x, y) for x, y in frame[["x", "y"]].to_numpy()]
    )
    assert isinstance(design.design(), Custom)
    assert design.design().points(SQUARE) == design.points()


def test_a_neural_emulator_learns_one_run_at_a_time():
    """The neural ensemble drives the variance criterion; it cannot condition a batch."""
    simulation = Simulation(wave, SQUARE, seed=1)
    settings = NeuralSettings(hidden=(8,), members=3, epochs=200)
    one = ActiveSettings(
        criterion="variance", emulator=NeuralEmulator, options={"settings": settings}
    )
    design = ActiveLearning(simulation, one).run(8)
    assert isinstance(design.emulator, NeuralEmulator)
    batch = ActiveSettings(
        criterion="variance",
        batch=2,
        emulator=NeuralEmulator,
        options={"settings": settings},
    )
    with pytest.raises(TypeError):
        ActiveLearning(simulation, batch).run(8)
    ivr = ActiveSettings(emulator=NeuralEmulator, options={"settings": settings})
    with pytest.raises(TypeError):
        ActiveLearning(simulation, ivr).run(7)


def test_settings_errors():
    """Unknown criteria, empty batches and too few runs are refused."""
    with pytest.raises(ValueError):
        ActiveSettings(criterion="nope")
    with pytest.raises(ValueError):
        ActiveSettings(batch=0)
    with pytest.raises(ValueError):
        ActiveSettings(initial=0)
    with pytest.raises(ValueError):
        ActiveLearning(Simulation(wave, SQUARE)).run(3)


def test_branin_benchmark():
    """Branin: 40 active runs match a hypercube of 50 (factor 1.25), not of 80.

    Measured with ``benchmarks/emulate/active_vs_lhs.py branin --runs 80``: the
    factor is 1.2 to 1.8 between 20 and 80 runs (40 active runs: error 0.015,
    the hypercube needs 51; 80: 0.0004, it needs 146), short of the roadmap's 2.
    """
    simulation = Simulation(branin, BRANIN, seed=1)
    units = np.random.default_rng(TEST_SEED).random((TEST_POINTS, 2))
    test = (units, simulation.evaluate(units, (2,)))
    assert active_error(simulation, 40, test) <= lhs_error(simulation, 50, test)


def test_bass_diffusion_benchmark():
    """Bass diffusion (zoo): 20 active runs match a hypercube of 40 (factor 2).

    The output is the share adopted after four years over the innovation and
    imitation rates, common random numbers for every run. Measured at 10,000
    households with 200 test runs: the factor 2 holds at 20 runs (error 0.0229
    against 0.0240) but not at 30 (0.0216 against 0.0178) or 40 (0.0180
    against 0.0159), where the run-to-run scatter starts to dominate both
    errors; the benchmark script (20,000 households) measures 1.6 to 2.9.
    """
    space = ScenarioSpace(
        innovation=(0.005, 0.05), imitation=(0.1, 0.8), households=BASS_HOUSEHOLDS
    )
    simulation = Simulation(
        BassDiffusion, space, ["adoption"], steps=BASS_STEPS, common=True, seed=1
    )
    units = np.random.default_rng(TEST_SEED).random((BASS_TEST_RUNS, 2))
    test = (units, simulation.evaluate(units, (2,)))
    assert active_error(simulation, 20, test) <= lhs_error(simulation, 40, test)
