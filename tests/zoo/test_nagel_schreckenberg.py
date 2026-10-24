"""Nagel-Schreckenberg: the fundamental diagram, and same seed same run."""

import numpy as np
import pytest

from modelly.zoo.nagel_schreckenberg.model import (
    NagelSchreckenberg,
    TrafficScenario,
    fundamental_diagram,
)

MAX_SPEED = 5
TRANSIENT = 300
MEASURED = 200
# Away from the critical density 1 / (MAX_SPEED + 1), where the transient is longest.
DENSITIES = (0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.8)
DAWDLE = 0.25
# Five standard deviations of a mean of independent Bernoulli dawdles.
Z_BOUND = 5.0


def test_deterministic_flow_is_exact():
    """Without dawdling the steady flow is ``min(rho * v_max, 1 - rho)`` exactly."""
    flows = fundamental_diagram(DENSITIES, TRANSIENT, MEASURED, rng=1, dawdle=0.0)
    expected = [min(rho * MAX_SPEED, 1 - rho) for rho in DENSITIES]
    assert flows == pytest.approx(expected, abs=1e-12)


def test_flow_rises_then_falls():
    """With dawdling the diagram peaks at an interior density."""
    flows = fundamental_diagram(DENSITIES, TRANSIENT, MEASURED, rng=2, dawdle=DAWDLE)
    peak = int(np.argmax(flows))
    assert 0 < peak < len(DENSITIES) - 1
    assert np.all(np.diff(flows[peak:]) < 0)  # the jammed branch falls steadily
    assert flows[0] < flows[peak]


def test_free_flow_speed_is_max_speed_minus_dawdle():
    """At low density each car runs at ``v_max - Bernoulli(dawdle)``.

    The mean speed over ``n`` cars and ``T`` steps then has standard deviation
    ``sqrt(dawdle (1 - dawdle) / (n T))``; the flow is the density times it.
    """
    density, length, steps = 0.02, 1000, 500
    (flow,) = fundamental_diagram(
        [density], TRANSIENT, steps, rng=3, dawdle=DAWDLE, length=length
    )
    cars = density * length
    sd = density * np.sqrt(DAWDLE * (1 - DAWDLE) / (cars * steps))
    assert abs(flow - density * (MAX_SPEED - DAWDLE)) < Z_BOUND * sd


def test_cars_never_collide():
    """Cars keep distinct cells, in road order, and their number is fixed."""
    model = NagelSchreckenberg(TrafficScenario(rng=4, density=0.6, steps=100))
    n = len(model.cars)
    model.run()
    assert len(model.cars) == n
    assert np.unique(model.cars.position).shape[0] == n
    assert np.all(model.gaps() >= 0)
    assert np.all(model.cars.velocity <= MAX_SPEED)


@pytest.mark.parametrize("density", [0.0, 1.5])
def test_impossible_density_is_rejected(density):
    """No cars, or more cars than cells, is an error."""
    with pytest.raises(ValueError, match="density"):
        NagelSchreckenberg(TrafficScenario(rng=1, density=density))


def test_same_seed_same_run():
    """Same seed, same flow series; another seed, another series."""

    def series(seed):
        model = NagelSchreckenberg(TrafficScenario(rng=seed, steps=100))
        model.run()
        return model.datacollector.get_model_vars_dataframe()

    assert series(5).equals(series(5))
    assert not series(5).equals(series(6))
