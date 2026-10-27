"""Tests for history matching: implausibility, waves, and a zoo SEIR wave sequence."""

import os
import subprocess
import sys
from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest

from modelly.emulate import (
    HistoryMatch,
    MatchSettings,
    Observation,
    Simulation,
    implausibility,
)
from modelly.emulate.base import unit_of
from modelly.emulate.history import CUTOFF, maximin
from modelly.experiments import ScenarioSpace
from modelly.zoo.age_seir.model import AgeSEIR
from tests.emulate.test_simulation import SEIR_OUTPUTS

ROOT = Path(__file__).resolve().parents[2]
TRUTH = {"beta": 0.035, "incubation": 0.25, "recovery": 0.2}  # the zoo defaults
SPACE = ScenarioSpace(beta=(0.01, 0.08), incubation=(0.1, 0.6), recovery=(0.1, 0.5))
STEPS = 150
OBSERVATION_ERROR = 0.05  # the data's error: 5 % of each observed value
TRUTH_REPLICATES = 8  # runs at the truth that measure the run-to-run scatter
WAVES, RUNS, CANDIDATES = 4, 20, 10_000


def test_implausibility_formula():
    """I = |z - mean| / sqrt(sd^2 + observation variance + discrepancy)."""
    observations = [Observation("y", 1.0, 0.5, 0.25)]
    value = implausibility(np.array([[4.0]]), np.array([[0.5]]), observations)
    assert value[0, 0] == pytest.approx(3.0 / np.sqrt(0.25 + 0.5 + 0.25))
    with pytest.raises(ValueError):
        Observation("y", 1.0, -1.0)


def test_maximin_spreads_points():
    """Maximin picks distinct points, far apart, and everything when asked for more."""
    region = np.random.default_rng(0).random((500, 2))
    chosen = maximin(region, 10, np.random.default_rng(1))
    gaps = np.sqrt(((chosen[:, None] - chosen[None]) ** 2).sum(2))
    assert len(np.unique(chosen, axis=0)) == 10
    assert gaps[np.triu_indices(10, 1)].min() > 0.15
    assert len(maximin(region[:5], 10, np.random.default_rng(1))) == 5


def test_definition_errors():
    """Observations must name outputs; rank must fit the observations."""
    simulation = Simulation(lambda a: a, ScenarioSpace(a=(0.0, 1.0)))
    with pytest.raises(ValueError):
        HistoryMatch(simulation, [Observation("nope", 0.5, 0.1)])
    with pytest.raises(ValueError):
        HistoryMatch(
            simulation, [Observation("output", 0.5, 0.1)], MatchSettings(rank=2)
        )
    with pytest.raises(ValueError):
        HistoryMatch(simulation, [Observation("output", 0.5, 0.1)]).run(1, runs=0)


def seir_observations():
    """Synthetic data: one run at the true parameters, scatter from replicates there."""
    fixed = ScenarioSpace(
        beta=(TRUTH["beta"], TRUTH["beta"] * 1.0001),
        incubation=TRUTH["incubation"],
        recovery=TRUTH["recovery"],
    )
    truth = Simulation(AgeSEIR, fixed, SEIR_OUTPUTS, steps=STEPS, seed=7)
    runs = truth.evaluate(np.zeros((TRUTH_REPLICATES, 1)), (1,))
    observed, scatter = runs[0], runs.var(axis=0)
    return [
        Observation(name, float(z), float((OBSERVATION_ERROR * z) ** 2), float(v))
        for name, z, v in zip(truth.names, observed, scatter)
    ]


def seir_match():
    """Four waves of twenty runs of the zoo's age-structured SEIR."""
    simulation = Simulation(AgeSEIR, SPACE, SEIR_OUTPUTS, steps=STEPS, seed=1)
    settings = MatchSettings(candidates=CANDIDATES)
    return HistoryMatch(simulation, seir_observations(), settings).run(WAVES, RUNS)


@pytest.fixture(name="seir", scope="module")
def fixture_seir():
    """The SEIR history match, run once for the tests that read it."""
    pytest.importorskip("pyarrow")
    return seir_match()


def test_seir_waves_shrink_around_the_truth(seir):
    """Each wave rules out more space; the true parameters are never ruled out."""
    volumes = seir.volumes
    assert len(volumes) == WAVES
    assert all(later < earlier for earlier, later in pairwise(volumes))
    assert volumes[0] < 0.5 and volumes[-1] < 0.05
    assert seir.contains(TRUTH)
    assert (seir.implausibility(unit_of(SPACE, TRUTH)[None, :]) <= CUTOFF).all()
    sample = seir.samples()
    assert len(sample) == round(volumes[-1] * CANDIDATES)
    for name, value in TRUTH.items():
        assert sample[name].min() < value < sample[name].max()
    table = seir.table()
    assert list(table.columns) == ["runs", "training", "volume"]
    assert (table["runs"] == RUNS).all()


def test_seir_waves_with_the_pure_python_core(seir, tmp_path):
    """MODELLY_PURE_PYTHON=1 in a fresh process rules out exactly the same space."""
    out = tmp_path / "alive.npy"
    code = (
        "import sys, numpy; from tests.emulate.test_history import seir_match; "
        "numpy.save(sys.argv[1], seir_match().alive)"
    )
    env = {**os.environ, "MODELLY_PURE_PYTHON": "1", "PYTHONPATH": str(ROOT)}
    subprocess.run(
        [sys.executable, "-c", code, str(out)], check=True, env=env, cwd=ROOT
    )
    np.testing.assert_array_equal(np.load(out), seir.alive)


def test_an_impossible_observation_empties_the_space():
    """Data no point can produce rule everything out; later waves do not run."""
    simulation = Simulation(lambda a: a, ScenarioSpace(a=(0.0, 1.0)), seed=2)
    observed = [Observation("output", 5.0, 1e-4)]
    match = HistoryMatch(simulation, observed, MatchSettings(candidates=500))
    result = match.run(waves=3, runs=8)
    assert result.volumes == [0.0]
    assert result.samples().empty


def linear_match():
    """A two-output linear match: two waves, then one more."""
    space = ScenarioSpace(a=(0.0, 1.0), b=(0.0, 1.0))
    simulation = Simulation(lambda a, b: [a + b, a - b], space, ["s", "d"], seed=4)
    observed = [Observation("s", 1.0, 1e-3), Observation("d", 0.2, 1e-3)]
    history = HistoryMatch(simulation, observed, MatchSettings(candidates=2000))
    history.run(2, runs=10)
    return history.run(1, runs=10)


def test_more_waves_continue_the_match():
    """run() again adds waves; the same seed gives the same waves."""
    first, second = linear_match(), linear_match()
    assert len(first.waves) == 3
    assert first.volumes == second.volumes
    np.testing.assert_array_equal(first.alive, second.alive)
    assert first.waves[2].training >= 10
    assert first.contains({"a": 0.6, "b": 0.4})
