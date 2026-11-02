"""``solve_batch`` against ``scipy.integrate.solve_ivp`` run once per system."""

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from modelly.couple.batch import solve_batch
from modelly.couple.events import Event
from modelly.couple.schedule import CouplingError

SYSTEMS = 200
# Same steps, same formulas: the two differ by the order of floating-point sums only.
ROUND_OFF = 1e-9


def viral(t, y, p):
    """Target-cell-limited viral load ``v`` and immune response ``i``, per system."""
    v, i = y[0], y[1]
    return np.array([p["r"] * v - p["c"] * v * i, p["a"] * v - p["d"] * i])


def decay(t, y, p):
    """``y' = -rate y``."""
    return -p["rate"] * y


def oscillator(t, y, p):
    """``x'' = -w**2 x`` as a first-order system."""
    return np.array([y[1], -(p["w"] ** 2) * y[0]])


def below_half(t, y, p):
    """Zero when the first variable is 0.5."""
    return y[0] - 0.5


def position(t, y, p):
    """The oscillator's position."""
    return y[0]


@pytest.fixture
def population():
    """Random parameters and initial states for ``viral``."""
    rng = np.random.default_rng(7)
    params = {
        "r": rng.uniform(0.5, 2.0, SYSTEMS),
        "c": rng.uniform(0.5, 1.5, SYSTEMS),
        "a": rng.uniform(0.1, 1.0, SYSTEMS),
        "d": 0.3,
    }
    y0 = np.vstack([rng.uniform(0.01, 1.0, SYSTEMS), np.zeros(SYSTEMS)])
    return params, y0


def one(params, j):
    """System ``j``'s parameters."""
    return {
        name: value[j] if np.ndim(value) else value for name, value in params.items()
    }


@pytest.mark.parametrize("method", ["RK45", "RK23"])
@pytest.mark.parametrize(("rtol", "atol"), [(1e-3, 1e-6), (1e-8, 1e-10)])
def test_every_system_takes_its_own_solve_ivp_steps(population, method, rtol, atol):
    """Each column gets ``solve_ivp``'s answer and its exact number of accepted steps."""
    params, y0 = population
    batch = solve_batch(
        viral, (0.0, 10.0), y0, params, method=method, rtol=rtol, atol=atol
    )
    for j in range(SYSTEMS):
        ref = solve_ivp(viral, (0.0, 10.0), y0[:, j], method=method, rtol=rtol, atol=atol,
                        args=(one(params, j),))  # fmt: skip
        assert batch.nsteps[j] == ref.t.size - 1
        np.testing.assert_allclose(
            batch.y[:, j], ref.y[:, -1], rtol=ROUND_OFF, atol=atol * 1e-3
        )
    assert np.all(batch.t == 10.0)


def test_each_system_has_its_own_time_span():
    """Spans given per system end each system at its own time."""
    rate = np.array([1.0, 1.0, 2.0])
    end = np.array([1.0, 2.0, 0.5])
    result = solve_batch(
        decay, (0.0, end), np.ones((1, 3)), {"rate": rate}, rtol=1e-10, atol=1e-12
    )
    np.testing.assert_allclose(result.y[0], np.exp(-rate * end), rtol=1e-8)
    np.testing.assert_array_equal(result.t, end)


def test_a_terminal_event_stops_each_system_at_its_crossing():
    """Exponential decay crosses one half at ``ln 2 / rate``; the state there is one half."""
    rate = np.linspace(0.5, 2.0, 50)
    event = Event(below_half, terminal=True, direction=-1)
    result = solve_batch(decay, (0.0, 10.0), np.ones((1, 50)), {"rate": rate},
                         rtol=1e-10, atol=1e-12, events=[event])  # fmt: skip
    assert result.stopped.all()
    np.testing.assert_allclose(result.t, np.log(2) / rate, rtol=1e-8)
    np.testing.assert_allclose(result.y[0], 0.5, rtol=1e-12)
    np.testing.assert_array_equal(result.events[0].rows, np.arange(50))


def test_non_terminal_events_record_every_crossing_in_its_direction():
    """``cos(w t)`` falls through zero at ``(2n + 1/2) pi / w``, rises at ``(2n + 3/2) pi / w``."""
    w = np.array([1.0, 2.0])
    y0 = np.array([[1.0, 1.0], [0.0, 0.0]])
    falling = Event(position, direction=-1)
    both = Event(position)
    result = solve_batch(oscillator, (0.0, 20.0), y0, {"w": w}, rtol=1e-10, atol=1e-12,
                         events=[falling, both])  # fmt: skip
    for j in range(2):
        down = result.events[0].t[result.events[0].rows == j]
        expected = (2 * np.arange(down.size) + 0.5) * np.pi / w[j]
        np.testing.assert_allclose(down, expected, rtol=1e-7)
        assert down.size == int(20.0 * w[j] / (2 * np.pi) + 0.75)
        crossings = np.sum(result.events[1].rows == j)
        assert crossings == int(20.0 * w[j] / np.pi + 0.5)
    assert not result.stopped.any()


def test_parameters_not_shaped_per_system_pass_whole():
    """A shared matrix is passed whole while per-system arrays are cut."""

    def linear(t, y, p):
        return p["rotation"] @ y * p["scale"]

    rotation = np.array([[0.0, 1.0], [-1.0, 0.0]])
    scale = np.array([1.0, 2.0, 3.0])
    y0 = np.vstack([np.ones(3), np.zeros(3)])
    result = solve_batch(
        linear,
        (0.0, 1.0),
        y0,
        {"rotation": rotation, "scale": scale},
        rtol=1e-10,
        atol=1e-12,
    )
    np.testing.assert_allclose(result.y[0], np.cos(scale), rtol=1e-8)


def test_an_unknown_method_is_refused():
    """Only the explicit pairs run batched."""
    with pytest.raises(CouplingError, match="RK45"):
        solve_batch(decay, (0.0, 1.0), np.ones((1, 2)), {"rate": 1.0}, method="BDF")


def test_a_system_ends_the_same_alone_or_in_a_crowd(population):
    """Every operation is per column, so a subset integrated alone gives the same bits."""
    params, y0 = population
    whole = solve_batch(viral, (0.0, 10.0), y0, params, rtol=1e-6, atol=1e-9)
    some = np.arange(0, SYSTEMS, 7)
    alone = solve_batch(
        viral, (0.0, 10.0), y0[:, some], one(params, some), rtol=1e-6, atol=1e-9
    )
    np.testing.assert_array_equal(alone.y, whole.y[:, some])
    np.testing.assert_array_equal(alone.nsteps, whole.nsteps[some])
