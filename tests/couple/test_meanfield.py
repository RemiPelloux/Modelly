"""The mean-field companion: the Bass zoo model's gap to its ODE shrinks like 1 / sqrt(N)."""

import numpy as np
import pytest

from modelly.couple.meanfield import (
    Companion,
    MeanField,
    bass,
    gap_by_size,
    lotka_volterra,
    sir,
)
from modelly.zoo.bass_diffusion.model import BassDiffusion, BassScenario

P, Q, DT, STEPS = 0.03, 0.38, 0.005, 1600


def adoption(model):
    """The Bass model's aggregate state."""
    return [model.adoption]


LIMIT = MeanField(bass, adoption, ("adopted",), {"innovation": P, "imitation": Q})


def run(households, seed):
    """A well-mixed Bass run with its companion."""
    model = BassDiffusion(BassScenario(rng=seed, households=households, dt=DT, steps=STEPS,
                                       innovation=P, imitation=Q))  # fmt: skip
    companion = Companion(model, LIMIT)
    for _ in range(STEPS):
        model.step()
        companion.advance(DT)
    return companion


def test_the_gap_shrinks_like_one_over_root_n():
    """Over sizes 250 to 16,000 the fitted exponent of the gap is about -1/2."""
    result = gap_by_size(run, [250, 1000, 4000, 16000], seeds=[1, 2, 3])
    assert result.exponent == pytest.approx(-0.5, abs=0.15)
    assert result.gaps[0] > result.gaps[-1]


def test_the_frame_holds_the_model_and_its_limit():
    """One row per recorded time; the limit equals the Bass solution."""
    companion = run(1000, 4)
    frame = companion.frame()
    assert list(frame.columns) == ["adopted", "adopted_limit"]
    t = frame.index.to_numpy()
    exact = (1 - np.exp(-(P + Q) * t)) / (1 + (Q / P) * np.exp(-(P + Q) * t))
    np.testing.assert_allclose(frame["adopted_limit"], exact, atol=1e-7)
    assert len(frame) == STEPS + 1 and companion.gap() > 0


def test_built_in_limits():
    """SIR conserves its total; Lotka-Volterra's first integral is constant."""
    y = np.array([0.99, 0.01, 0.0])
    assert sir(0.0, y, {"beta": 0.3, "gamma": 0.1}).sum() == pytest.approx(0.0)
    p = {"a": 1.0, "b": 1.0, "c": 1.0, "d": 1.0}
    x, z = 0.5, 2.0
    dx, dz = lotka_volterra(0.0, np.array([x, z]), p)
    # V = d x - c ln x + b y - a ln y is constant: dV = (d - c/x) dx + (b - a/z) dz = 0.
    assert (1 - 1 / x) * dx + (1 - 1 / z) * dz == pytest.approx(0.0)
