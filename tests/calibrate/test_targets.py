"""Tests for Target: alignment, summaries, weights and errors."""

import numpy as np
import pytest

from modelly.calibrate import Target
from modelly.calibrate.targets import total_distance
from tests.calibrate.models import peak


def test_target_aligns_the_end_of_the_series():
    """Observed values are matched to the last steps, replicates averaged."""
    target = Target("x", [2.0, 3.0])
    series = np.array([[0.0, 1.0, 2.0, 3.0], [0.0, 1.0, 4.0, 5.0]])
    np.testing.assert_allclose(target.simulated(series), [3.0, 4.0])
    assert target.score(np.array([2.0, 3.0])) == 0.0


def test_target_summary_and_weight():
    """A summary turns each replicate's series into the compared statistics."""
    target = Target("x", [5.0], summary=peak, distance="mae", weight=2.0)
    series = np.array([[0.0, 4.0, 1.0], [0.0, 2.0, 2.0]])
    np.testing.assert_allclose(target.simulated(series), [3.0])
    assert target.score(target.simulated(series)) == pytest.approx(4.0)
    assert target.spec == "x"
    second = Target("y", [0.0], output="value")
    assert second.spec == "value"
    total = total_distance(
        [target, second], {"x": np.array([5.0]), "y": np.array([1.0])}
    )
    assert total == pytest.approx(1.0)


def test_target_errors():
    """An unknown distance name, a negative weight and too long a series are refused."""
    with pytest.raises(ValueError):
        Target("x", [1.0], distance="nope")
    with pytest.raises(ValueError):
        Target("x", [1.0], weight=-1)
    with pytest.raises(ValueError):
        Target("x", np.zeros(12)).check_length(10)
    Target("x", np.zeros(11)).check_length(10)
