"""Tests for Simulation: functions and models turned into ``values[point, output]``."""

import numpy as np
import pytest

from modelly.emulate import Simulation
from modelly.experiments import ScenarioSpace
from modelly.zoo.age_seir.model import AgeSEIR
from tests.emulate.models import peak_step

SPACE = ScenarioSpace(a=(0.0, 2.0), b=(0.0, 1.0))
SEIR_SPACE = ScenarioSpace(beta=(0.02, 0.05), recovery=(0.15, 0.3))
SEIR_OUTPUTS = {
    "peak": ("tests.emulate.models:infectious", "max"),
    "timing": ("tests.emulate.models:infectious", peak_step),
    "size": "tests.emulate.models:recovered",
}


def test_function_outputs_in_column_order():
    """A function may return a number, a sequence or a mapping."""
    units = np.array([[0.5, 0.5], [0.25, 1.0]])
    single = Simulation(lambda a, b: a * b, SPACE).evaluate(units, (1,))
    np.testing.assert_allclose(single, [[0.5], [0.5]])
    pairs = Simulation(lambda a, b: (a, b), SPACE, ["a", "b"])
    np.testing.assert_allclose(pairs.evaluate(units, (1,)), [[1.0, 0.5], [0.5, 1.0]])
    mapping = Simulation(lambda a, b: {"b": b, "a": a}, SPACE, ["a", "b"])
    np.testing.assert_allclose(mapping.evaluate(units, (1,)), [[1.0, 0.5], [0.5, 1.0]])
    with pytest.raises(ValueError):
        Simulation(lambda a, b: a, SPACE, ["a", "b"]).evaluate(units, (1,))


def test_definition_errors():
    """No varying parameter, no model output, or an unknown statistic are refused."""
    with pytest.raises(ValueError):
        Simulation(lambda a: a, ScenarioSpace(a=1.0))
    with pytest.raises(ValueError):
        Simulation(AgeSEIR, SEIR_SPACE)
    with pytest.raises(ValueError):
        Simulation(AgeSEIR, SEIR_SPACE, {"peak": ("infected", "median")})


def test_model_outputs_and_statistics():
    """A model's outputs are reduced by their statistics; the same key reruns nothing new."""
    pytest.importorskip("pyarrow")
    simulation = Simulation(AgeSEIR, SEIR_SPACE, SEIR_OUTPUTS, steps=150, seed=3)
    units = np.array([[0.8, 0.2], [0.1, 0.9]])
    values = simulation.evaluate(units, (1,))
    assert simulation.names == ["peak", "timing", "size"]
    assert values.shape == (2, 3)
    assert values[0, 0] > values[1, 0]  # a larger R0 peaks higher...
    assert values[0, 2] > values[1, 2]  # ...and infects more people
    np.testing.assert_array_equal(simulation.evaluate(units, (1,)), values)


def test_common_random_numbers():
    """With common=True every point runs with the same seeds, whatever its batch."""
    pytest.importorskip("pyarrow")
    common = Simulation(
        AgeSEIR, SEIR_SPACE, SEIR_OUTPUTS, steps=60, seed=3, common=True
    )
    point = np.array([[0.5, 0.5]])
    alone = common.evaluate(point, (1,))
    among = common.evaluate(np.vstack([[0.1, 0.1], point[0]]), (2,))
    np.testing.assert_array_equal(among[1], alone[0])
