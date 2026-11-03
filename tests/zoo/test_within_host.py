"""Within-host epidemic: every host's ODE is its own solve_ivp call; analytic clearance."""

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from modelly.couple.events import ODEEvent
from modelly.zoo.within_host.model import (
    STATE,
    Host,
    WithinHost,
    WithinHostScenario,
)

# Same steps, same formulas: the batch and solve_ivp differ by summation order only.
ROUND_OFF = 1e-8


def outbreak(**changes):
    """A small outbreak, run to day ten, where many hosts are mid-infection."""
    model = WithinHost(WithinHostScenario(rng=4, hosts=400, contacts=12.0, **changes))
    model.run(10)
    return model


def state(model):
    """Every host's ``(cells, infected, virus)``, shape (3, hosts)."""
    table = model.columns[Host]
    return np.array([table[name] for name in STATE])


def test_each_host_follows_its_own_solve_ivp_call():
    """One day of the batch equals one ``solve_ivp`` call per host, states and onsets."""
    model = outbreak()
    s, table = model.scenario, model.columns[Host]
    start, y0 = float(model.time), state(model)
    before = table.infectious.copy()
    model.ode.advance(start, 1.0)
    rhs, level = model.ode.rhs, model.ode.events[0].condition
    exposed = np.flatnonzero(table.exposed)
    assert exposed.size > 50
    for j in exposed:
        p = {"beta": table.beta[j]}
        rise = ODEEvent(level, direction=1)
        ref = solve_ivp(lambda t, y, p=p: rhs(t, y, p), (start, start + 1.0), y0[:, j],
                        rtol=s.rtol, atol=s.atol, events=_scalar(rise, p))  # fmt: skip
        np.testing.assert_allclose(
            state(model)[:, j], ref.y[:, -1], rtol=ROUND_OFF, atol=s.atol
        )
        if ref.t_events[0].size and not before[j]:
            assert table.onset[j] == pytest.approx(ref.t_events[0][0], rel=1e-9)


def _scalar(event, p):
    """``event`` as a ``solve_ivp`` event function of one host."""

    def function(t, y):
        return float(event.condition(np.array([t]), y[:, None], p)[0])

    function.direction = event.direction
    return function


def test_clearance_without_target_cells_is_exponential():
    """With no cells to infect, ``V = V0 exp(-c t)`` crosses the threshold at a known time."""
    model = WithinHost(WithinHostScenario(rng=1, hosts=50, index_cases=0, contacts=0.0))
    s, table = model.scenario, model.columns[Host]
    loads = np.geomspace(0.02, 5.0, 50)
    table.cells[:], table.virus[:], table.exposed[:] = 0.0, loads, True
    model.run(5)
    exact = np.log(loads / s.threshold) / s.clearance
    np.testing.assert_allclose(table.cleared, exact, rtol=1e-6)
    assert not table.infectious.any()


def test_cells_stay_in_range_and_cells_are_conserved():
    """``T`` and ``I`` stay in [0, 1]; ``T + I`` only falls, as infected cells die."""
    model = outbreak()
    table = model.columns[Host]
    cells, infected = table.cells, table.infected
    assert cells.min() >= -1e-9 and infected.min() >= -1e-9
    assert np.all(cells + infected <= 1.0 + 1e-9)


def test_an_epidemic_needs_contacts():
    """With contacts most hosts are exposed; without, only the index cases."""
    assert outbreak().attack_rate() > 0.5
    quiet = WithinHost(WithinHostScenario(rng=4, hosts=400, contacts=0.0))
    quiet.run(20)
    assert quiet.columns[Host].exposed.sum() == quiet.scenario.index_cases
    assert np.isfinite(quiet.columns[Host].onset[:10]).all()


def test_same_seed_same_outbreak_straight_or_resumed(tmp_path):
    """Two runs with one seed agree bit for bit, and so does a run resumed from a checkpoint."""
    straight = outbreak()
    resumed = WithinHost(WithinHostScenario(rng=4, hosts=400, contacts=12.0))
    resumed.run(4)
    resumed.save(tmp_path / "host.ckpt")
    loaded = WithinHost.load(tmp_path / "host.ckpt")
    loaded.run(6)
    for name in (*STATE, "onset", "cleared", "exposed"):
        np.testing.assert_array_equal(
            loaded.columns[Host][name], straight.columns[Host][name]
        )
    np.testing.assert_array_equal(state(outbreak()), state(straight))
