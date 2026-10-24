"""Tests for OAT, Morris, PAWN and the emulator on functions and a model."""

import numpy as np
import pytest

from modelly.experiments import ScenarioSpace
from modelly.sensitivity import emulate, morris, oat, pawn, sobol
from modelly.sensitivity.screening import morris_design
from tests.sensitivity.models import Response, ishigami
from tests.sensitivity.test_variance import ISHIGAMI

pytest.importorskip("pyarrow")

SPACE = ScenarioSpace(a=(0.0, 1.0), b=(0.0, 1.0), c=(0.0, 1.0), d=(0.0, 1.0))
RANKING = ["a", "b", "c", "d"]


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_morris_ranking_is_stable_across_seeds(seed):
    """The model's inputs rank the same way whatever the seed."""
    screen = morris(Response, SPACE, "value", trajectories=8, steps=1, seed=seed)
    assert list(screen.ranking().index) == RANKING
    assert screen.table.loc["d", "mu_star"] < screen.table.loc["c", "mu_star"] / 2
    assert screen.info["evaluations"] == 8 * 5


def test_morris_design():
    """Each step moves one factor by plus or minus delta, every factor once."""
    points, moved, steps = morris_design(3, 4, 4, np.random.default_rng(1))
    assert points.shape == (4, 4, 3)
    assert ((points >= 0) & (points <= 1)).all()
    for t in range(4):
        assert sorted(moved[t]) == [0, 1, 2]
        changes = np.diff(points[t], axis=0)
        assert (np.count_nonzero(changes, axis=1) == 1).all()
        np.testing.assert_allclose(np.abs(steps[t]), 2 / 3)
    with pytest.raises(ValueError):
        morris(ishigami, ISHIGAMI, trajectories=1)


def test_oat_sweeps():
    """One sweep per parameter; the effect is the output's range along it."""
    space = ScenarioSpace(x1=(-1.0, 1.0), policy=["low", "high"], n=3)
    result = oat(lambda x1, policy, n: x1 + (policy == "high"), space, levels=3)
    assert result.table.loc["x1", "effect"] == pytest.approx(2.0)
    assert result.table.loc["policy", "effect"] == pytest.approx(1.0)
    assert len(result.sweeps) == 3 + 2
    frame = result.to_dataframe()
    assert list(frame["parameter"]) == ["x1", "policy"]


def test_pawn_ranks_ishigami():
    """PAWN finds x2 and x1 more influential than x3 on the Ishigami function."""
    result = pawn(ishigami, ISHIGAMI, samples=400, slices=8, seed=1)
    assert result.ranking().index[-1] == "x3"
    assert ((result.table >= 0) & (result.table <= 1)).all().all()
    with pytest.raises(ValueError):
        pawn(ishigami, ISHIGAMI, samples=10, slices=8)
    with pytest.raises(ValueError):
        pawn(ishigami, ISHIGAMI, summary="nope")


def test_emulator_stands_in_for_the_model():
    """A Gaussian process fitted to 60 runs gives the model's Sobol ranking."""
    surrogate = emulate(Response, SPACE, "value", samples=60, steps=1, seed=1)
    assert surrogate.r2 > 0.9
    result = sobol(surrogate, SPACE, samples=512, seed=1)
    assert list(result.ranking().index[:2]) == ["a", "b"]
    with pytest.raises(ValueError):
        sobol(surrogate, ISHIGAMI, samples=8)


def test_plots():
    """Every result draws a figure."""
    pytest.importorskip("matplotlib")
    screen = morris(ishigami, ISHIGAMI, trajectories=4)
    assert screen.plot().axes and screen.plot().axes[0].get_xlabel().startswith("mu*")
    assert sobol(ishigami, ISHIGAMI, samples=64, bootstrap=10).plot().axes
    assert oat(ishigami, ISHIGAMI, levels=3).plot().axes
    assert pawn(ishigami, ISHIGAMI, samples=40, slices=4).plot().axes
    assert "morris" in repr(screen)


def test_study_errors():
    """A model needs an output; the space needs a varying parameter."""
    with pytest.raises(ValueError):
        morris(Response, SPACE)
    with pytest.raises(ValueError):
        morris(ishigami, ScenarioSpace(x1=1.0))
    with pytest.raises(ValueError):
        morris(Response, SPACE, "value", statistic="median")
