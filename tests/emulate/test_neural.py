"""Tests for the numpy neural-network ensemble emulator."""

import numpy as np
import pytest

from modelly.emulate import NeuralEmulator, NeuralSettings
from modelly.emulate.neural import _forward, _gradients, _initial

SMALL = NeuralSettings(hidden=(16,), members=3, epochs=600, seed=2)


def curve(units):
    """A smooth function of two inputs, and a second output of another scale."""
    first = np.sin(3 * units[:, 0]) * units[:, 1]
    return np.column_stack([first, 50 + 10 * units[:, 0]])


@pytest.fixture(name="data")
def fixture_data():
    """Sixty random points of the unit square and their outputs."""
    units = np.random.default_rng(1).random((60, 2))
    return units, curve(units)


def test_backpropagation_matches_finite_differences():
    """The gradient of one weight is the finite-difference slope of the loss."""
    rng = np.random.default_rng(0)
    layers = _initial([2, 5, 1], rng)
    x, y = rng.random((7, 2)), rng.random((7, 1))

    def loss(network):
        """The mean squared error of ``network`` on (x, y)."""
        return float(np.mean((_forward(network, x)[-1] - y) ** 2))

    analytic = _gradients(layers, x, y, 0.0)[0][0][1, 3]
    step = 1e-6
    shifted = [(w.copy(), b.copy()) for w, b in layers]
    shifted[0][0][1, 3] += step
    assert analytic == pytest.approx((loss(shifted) - loss(layers)) / step, rel=1e-3)


def test_ensemble_learns_both_outputs(data):
    """Each output is learned on its own scale; the spread is positive."""
    units, values = data
    emulator = NeuralEmulator.fit(units, values, ["wave", "line"], settings=SMALL)
    test = np.random.default_rng(9).random((200, 2))
    scores = emulator.score(test, curve(test))
    assert scores["wave"] < 0.2
    assert scores["line"] < 0.1
    mean, sd = emulator.predict(test)
    assert mean.shape == sd.shape == (200, 2)
    assert (sd >= 0).all() and sd.mean() > 0
    np.testing.assert_allclose(emulator.select("line").predict_unit(test), mean[:, 1])


def test_same_seed_same_emulator(data):
    """Training is deterministic for a seed and changes with it."""
    units, values = data
    test = np.random.default_rng(9).random((20, 2))
    first = NeuralEmulator.fit(units, values, settings=SMALL).predict(test)[0]
    again = NeuralEmulator.fit(units, values, settings=SMALL).predict(test)[0]
    other = NeuralSettings(hidden=(16,), members=3, epochs=600, seed=3)
    moved = NeuralEmulator.fit(units, values, settings=other).predict(test)[0]
    np.testing.assert_array_equal(first, again)
    assert not np.array_equal(first, moved)
