"""``AgentODE``: per-agent ODEs in columns, with events, inputs, stiff methods and checkpoints."""

import numpy as np
import pytest

from modelly import Agent, Model
from modelly.core.columns import Column
from modelly.couple.agent_ode import AgentODE
from modelly.couple.events import ODEEvent
from modelly.couple.ode import Solver
from modelly.couple.schedule import Coupling, CouplingError, Phase

TIGHT = Solver(rtol=1e-10, atol=1e-12)


class Neuron(Agent):
    """A leaky integrate-and-fire neuron: potential ``v``, drive ``current``, spike count."""

    v = Column(float, default=0.0)
    current = Column(float, default=2.0)
    spikes = Column(int, default=0)

    def __init__(self, model, current):
        """A neuron at rest with drive ``current``."""
        super().__init__(model)
        self.current = current


def leak(t, y, p):
    """``v' = current - v``, plus the coupling's ``bias``."""
    return p["current"] - y + p.get("bias", 0.0)


def threshold(t, y, p):
    """Zero when the potential reaches 1."""
    return y[0] - 1.0


def fire(table, rows, times):
    """Count the spike and reset the potential."""
    np.add.at(table["spikes"], rows, 1)
    table["v"][rows] = 0.0


SPIKE = ODEEvent(threshold, terminal=True, direction=1, action=fire)


def neurons(currents):
    """A model with one neuron per drive."""
    model = Model(rng=3)
    Neuron.create_agents(model, len(currents), current=list(currents))
    return model


def test_each_agent_follows_its_closed_form():
    """``v(t) = I (1 - e^{-t})`` from rest, below threshold."""
    currents = np.array([0.2, 0.5, 0.9])
    model = neurons(currents)
    AgentODE(model, Neuron, leak, ["v"], ["current"], solver=TIGHT).advance(0.0, 3.0)
    np.testing.assert_allclose(
        model.columns[Neuron].v, currents * (1 - np.exp(-3.0)), rtol=1e-9
    )


def test_terminal_events_fire_reset_and_resume_within_the_step():
    """Integrate-and-fire spikes every ``ln(I / (I - 1))``; counted over ten time units."""
    currents = np.array([1.5, 2.0, 4.0, 8.0])
    model = neurons(currents)
    ode = AgentODE(
        model, Neuron, leak, ["v"], ["current"], solver=TIGHT, events=[SPIKE]
    )
    ode.advance(0.0, 10.0)
    period = np.log(currents / (currents - 1))
    table = model.columns[Neuron]
    np.testing.assert_array_equal(table["spikes"], np.floor(10.0 / period).astype(int))
    after_last = 10.0 - np.floor(10.0 / period) * period
    np.testing.assert_allclose(
        table["v"], currents * (1 - np.exp(-after_last)), rtol=1e-7
    )


@pytest.mark.parametrize("method", ["BDF", "Radau", "LSODA"])
def test_stiff_methods_agree_with_the_batched_one(method):
    """The stacked path, with its block-diagonal sparsity, gives the same answer."""
    currents = np.linspace(0.1, 0.9, 20)
    explicit, stiff = neurons(currents), neurons(currents)
    AgentODE(explicit, Neuron, leak, ["v"], ["current"], solver=TIGHT).advance(0.0, 2.0)
    solver = Solver(method=method, rtol=1e-10, atol=1e-12)
    AgentODE(stiff, Neuron, leak, ["v"], ["current"], solver=solver).advance(0.0, 2.0)
    np.testing.assert_allclose(
        stiff.columns[Neuron].v, explicit.columns[Neuron].v, rtol=1e-7
    )


def test_coupling_inputs_reach_the_right_hand_side():
    """A ``bias`` quantity, held over the step, adds to every agent's drive."""
    model = neurons([0.0, 0.0])
    coupling = Coupling()
    coupling.add(Phase(int, writes=("bias",), initial={"bias": 0.5}))
    coupling.add(
        AgentODE(model, Neuron, leak, ["v"], ["current"], reads=["bias"], solver=TIGHT),
        1,
    )
    coupling.build()
    coupling.step()
    np.testing.assert_allclose(
        model.columns[Neuron].v, 0.5 * (1 - np.exp(-1.0)), rtol=1e-9
    )


def test_agents_added_and_removed_between_steps():
    """The batch follows the population; a newcomer starts from its column default."""
    model = neurons([0.5, 0.5, 0.5])
    ode = AgentODE(model, Neuron, leak, ["v"], ["current"], solver=TIGHT)
    ode.advance(0.0, 1.0)
    model.columns[Neuron].agents[0].remove()
    Neuron(model, 0.5)
    ode.advance(1.0, 1.0)
    v = model.columns[Neuron].v
    np.testing.assert_allclose(
        sorted(v),
        sorted([0.5 * (1 - np.exp(-2.0))] * 2 + [0.5 * (1 - np.exp(-1.0))]),
        rtol=1e-9,
    )


class Spiking(Model):
    """Neurons driven by ``AgentODE`` inside a coupling, saved with the model."""

    def __init__(self, rng=5):
        """Three neurons with different drives."""
        super().__init__(rng=rng)
        Neuron.create_agents(self, 3, current=[1.5, 3.0, 6.0])
        self.coupling = Coupling()
        self.coupling.add(
            AgentODE(self, Neuron, leak, ["v"], ["current"], events=[SPIKE])
        )
        self.coupling.build()

    def step(self):
        """One coupled step."""
        self.coupling.step()


def test_a_resumed_run_equals_a_straight_one(tmp_path):
    """Saved after five steps and loaded, the columns end bit for bit as a straight run."""
    straight = Spiking()
    straight.run_for(10)
    resumed = Spiking()
    resumed.run_for(5)
    resumed.save(tmp_path / "spiking.ckpt")
    loaded = Spiking.load(tmp_path / "spiking.ckpt")
    loaded.run_for(5)
    for name in ("v", "spikes"):
        np.testing.assert_array_equal(
            loaded.columns[Neuron][name], straight.columns[Neuron][name]
        )
    assert straight.columns[Neuron]["spikes"].min() > 0


def test_no_agents_is_a_no_op_and_bad_settings_are_refused():
    """An empty class does nothing; events need an explicit method; unknown methods fail."""
    AgentODE(Model(rng=1), Neuron, leak, ["v"]).advance(0.0, 1.0)
    with pytest.raises(CouplingError, match="explicit"):
        AgentODE(
            Model(rng=1),
            Neuron,
            leak,
            ["v"],
            solver=Solver(method="BDF"),
            events=[SPIKE],
        )
    with pytest.raises(CouplingError, match="supports"):
        AgentODE(Model(rng=1), Neuron, leak, ["v"], solver=Solver(method="Euler"))
