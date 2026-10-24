"""Tests for the distances: values and errors."""

import numpy as np
import pytest

from modelly.calibrate import distance

A, B = np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 6.0])


def test_distances():
    """The built-in distances on a known pair."""
    assert distance.rmse(A, B) == pytest.approx(np.sqrt(3.0))
    assert distance.mae(A, B) == pytest.approx(1.0)
    assert distance.euclidean(A, B) == pytest.approx(3.0)
    assert distance.weighted([0, 0, 1])(A, B) == pytest.approx(3.0)
    assert distance.weighted([1, 1, 0])(A, B) == 0.0
    assert distance.wasserstein(A, A[::-1]) == 0.0
    assert distance.wasserstein([0.0], [1.0, 1.0]) == pytest.approx(1.0)


def test_distance_errors():
    """Mismatched sizes and bad weights are a ValueError."""
    with pytest.raises(ValueError):
        distance.rmse(A, B[:2])
    with pytest.raises(ValueError):
        distance.weighted([1.0])(A, B)
    with pytest.raises(ValueError):
        distance.weighted([0.0, 0.0])
    with pytest.raises(ValueError):
        distance.weighted([-1.0, 2.0])
