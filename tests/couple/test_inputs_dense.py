"""Inputs that vary inside a step and dense output, against ``solve_ivp``."""

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from modelly import Model
from modelly.couple.agent_ode import AgentODE
from modelly.couple.batch import solve_batch
from modelly.couple.events import ODEEvent
from modelly.couple.inputs import Forcing, Series
from modelly.couple.ode import Solver
from modelly.couple.schedule import CouplingError
from tests.couple.test_agent_ode import SPIKE, TIGHT, Neuron, leak, neurons

ROUND_OFF = 1e-9
SYSTEMS = 50


def daily(t):
    """A drive that follows the time of day."""
    return 1.0 + np.sin(2 * np.pi * t)


def driven(t, y, p):
    """``y' = drive(t) * rate - y``."""
    return p["drive"] * p["rate"] - y


def test_series_reads_linearly_or_as_the_last_value():
    """Linear between the points, held before and after; ``previous`` holds each value."""
    times, values = [0.0, 1.0, 3.0], [0.0, 2.0, 0.0]
    t = np.array([-1.0, 0.5, 2.0, 4.0])
    assert Series(times, values)(t).tolist() == [0.0, 1.0, 1.0, 0.0]
    assert Series(times, values, "previous")(t).tolist() == [0.0, 0.0, 2.0, 0.0]
    per_system = Series([0.0, 1.0], [[0.0, 10.0], [1.0, 20.0]])
    assert per_system(np.array([0.5, 0.5])).tolist() == [0.5, 15.0]
    assert per_system.cut(np.array([1]), 2)(np.array([1.0])).tolist() == [20.0]


@pytest.mark.parametrize(
    ("times", "values", "kind"),
    [([1.0, 0.0], [0, 1], "linear"), ([0.0, 1.0], [0], "linear"), ([0.0], [1], "x")],
)
def test_bad_series_are_refused(times, values, kind):
    """Decreasing times, a row count that differs, an unknown kind."""
    with pytest.raises(ValueError, match="Series"):
        Series(times, values, kind)


def test_a_forcing_drives_each_system_as_in_solve_ivp():
    """Same steps and same answer as ``solve_ivp`` with the drive inside the function."""
    rates = np.linspace(0.5, 3.0, SYSTEMS)
    y0 = np.zeros((1, SYSTEMS))
    params = {"drive": Forcing(daily), "rate": rates}
    batch = solve_batch(driven, (0.0, 3.0), y0, params, rtol=1e-8, atol=1e-10)
    for j in range(SYSTEMS):
        ref = solve_ivp(lambda t, y, r=rates[j]: daily(t) * r - y, (0.0, 3.0), [0.0],
                        rtol=1e-8, atol=1e-10)  # fmt: skip
        assert batch.nsteps[j] == ref.t.size - 1
        np.testing.assert_allclose(batch.y[0, j], ref.y[0, -1], rtol=ROUND_OFF)


def test_a_per_system_series_is_cut_with_its_systems():
    """A system's result is the same, bit for bit, alone or among the others."""
    rng = np.random.default_rng(2)
    values = rng.uniform(0.0, 2.0, (5, SYSTEMS))
    params = {"drive": Series(np.linspace(0, 2, 5), values), "rate": 1.0}
    y0 = rng.uniform(0, 1, (1, SYSTEMS))
    spans = (0.0, rng.uniform(0.5, 2.0, SYSTEMS))
    together = solve_batch(driven, spans, y0, params)
    j = 17
    alone = {"drive": Series(np.linspace(0, 2, 5), values[:, [j]]), "rate": 1.0}
    single = solve_batch(driven, (0.0, spans[1][[j]]), y0[:, [j]], alone)
    assert together.y[0, j] == single.y[0, 0]


def test_dense_output_matches_solve_ivps_interpolant():
    """``sol(t)`` per system equals ``solve_ivp(dense_output=True).sol(t)``."""
    rates = np.linspace(0.5, 3.0, SYSTEMS)
    params = {"drive": Forcing(daily), "rate": rates}
    batch = solve_batch(driven, (0.0, 3.0), np.zeros((1, SYSTEMS)), params,
                        rtol=1e-6, atol=1e-9, dense_output=True)  # fmt: skip
    t = np.linspace(0.0, 3.0, SYSTEMS)
    values = batch.sol(t)
    for j in range(SYSTEMS):
        ref = solve_ivp(lambda s, y, r=rates[j]: daily(s) * r - y, (0.0, 3.0), [0.0],
                        rtol=1e-6, atol=1e-9, dense_output=True)  # fmt: skip
        np.testing.assert_allclose(
            values[0, j], ref.sol(t[j])[0], rtol=1e-8, atol=1e-12
        )
    np.testing.assert_array_equal(batch.sol(3.0), batch.y)
    np.testing.assert_array_equal(batch.sol(0.0), np.zeros((1, SYSTEMS)))


def test_dense_output_ends_at_a_terminal_event():
    """A stopped system is read up to its crossing and refused past it."""

    def decay(t, y, p):
        return -y

    half = ODEEvent(lambda t, y, p: y[0] - 0.5, terminal=True)
    batch = solve_batch(decay, (0.0, 2.0), np.ones((1, 2)), events=[half],
                        rtol=1e-10, atol=1e-12, dense_output=True)  # fmt: skip
    np.testing.assert_allclose(batch.sol.final, np.log(2), rtol=1e-9)
    np.testing.assert_allclose(batch.sol(np.log(2) / 2), np.sqrt(0.5), rtol=1e-8)
    with pytest.raises(ValueError, match="outside"):
        batch.sol(1.0)


def test_agent_ode_at_reads_the_continuous_state_inside_the_step():
    """Below threshold ``v(t) = I (1 - e^-t)`` at any time of the step, per agent."""
    currents = np.array([0.2, 0.5, 0.9])
    model = neurons(currents)
    ode = AgentODE(model, Neuron, leak, ["v"], ["current"], solver=TIGHT,
                   dense_output=True)  # fmt: skip
    ode.advance(1.0, 2.0)
    t = np.array([1.0, 2.0, 2.7])
    start = currents * (1 - np.exp(-0.0))
    assert np.all(start == 0)
    np.testing.assert_allclose(ode.at(t, "v"), currents * (1 - np.exp(-(t - 1.0))),
                               rtol=1e-8, atol=1e-12)  # fmt: skip
    np.testing.assert_allclose(ode.at(3.0)[0], model.columns[Neuron].v, rtol=1e-12)


def test_agent_ode_at_follows_the_reset_after_a_spike():
    """Just after its crossing a neuron reads near zero, just before near one."""
    model = neurons([2.0])
    ode = AgentODE(model, Neuron, leak, ["v"], ["current"], solver=TIGHT,
                   events=[SPIKE], dense_output=True)  # fmt: skip
    ode.advance(0.0, 1.0)
    crossing = np.log(2.0)
    assert ode.at(crossing - 1e-6, "v")[0] == pytest.approx(1.0, abs=1e-5)
    assert ode.at(crossing + 1e-6, "v")[0] == pytest.approx(0.0, abs=1e-5)


@pytest.mark.parametrize("method", ["BDF", "Radau"])
def test_stiff_methods_take_forcings_and_dense_output(method):
    """The stacked path evaluates the forcing at its own times and reads inside the step."""
    model, reference = neurons([0.5, 1.0]), neurons([0.5, 1.0])
    drive = {"bias": Forcing(daily)}
    stiff = AgentODE(model, Neuron, leak, ["v"], ["current"], forcings=drive,
                     solver=Solver(method=method, rtol=1e-9, atol=1e-11), dense_output=True)  # fmt: skip
    explicit = AgentODE(reference, Neuron, leak, ["v"], ["current"], forcings=drive,
                        solver=TIGHT, dense_output=True)  # fmt: skip
    stiff.advance(0.0, 1.0)
    explicit.advance(0.0, 1.0)
    t = np.array([0.3, 0.8])
    np.testing.assert_allclose(stiff.at(t), explicit.at(t), rtol=1e-5)


def test_at_refuses_without_dense_output_or_after_the_population_changed():
    """Each misuse names what is missing."""
    model = neurons([0.5, 0.5])
    plain = AgentODE(model, Neuron, leak, ["v"], ["current"])
    plain.advance(0.0, 1.0)
    with pytest.raises(CouplingError, match="dense_output"):
        plain.at(0.5)
    dense = AgentODE(model, Neuron, leak, ["v"], ["current"], dense_output=True)
    dense.advance(1.0, 1.0)
    with pytest.raises(ValueError, match="inside the last step"):
        dense.at(0.5)
    Neuron(model, 0.5)
    with pytest.raises(CouplingError, match="agents changed"):
        dense.at(1.5)


class Forced(Model):
    """Neurons with a daily forcing and dense output, saved with the model."""

    def __init__(self, rng=5):
        """Three neurons."""
        super().__init__(rng=rng)
        Neuron.create_agents(self, 3, current=[0.5, 1.5, 3.0])
        self.ode = AgentODE(self, Neuron, leak, ["v"], ["current"], events=[SPIKE],
                            forcings={"bias": Forcing(daily)}, dense_output=True)  # fmt: skip

    def step(self):
        """One unit of time."""
        self.ode.advance(float(self.time), 1.0)


def test_a_forced_model_resumes_bit_for_bit(tmp_path):
    """Forcings and the dense output survive a checkpoint."""
    straight = Forced()
    straight.run_for(6)
    resumed = Forced()
    resumed.run_for(3)
    resumed.save(tmp_path / "forced.ckpt")
    loaded = Forced.load(tmp_path / "forced.ckpt")
    np.testing.assert_array_equal(loaded.ode.at(3.5), resumed.ode.at(3.5))
    loaded.run_for(3)
    for name in ("v", "spikes"):
        np.testing.assert_array_equal(
            loaded.columns[Neuron][name], straight.columns[Neuron][name]
        )
