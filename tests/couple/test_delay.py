"""Delay equations: the method of steps against a closed form, births, checkpoints."""

import numpy as np
import pytest

from modelly import Agent, Model
from modelly.core.columns import Column
from modelly.couple.agent_ode import AgentODE
from modelly.couple.delay import Delay, chunks
from modelly.couple.ode import Solver
from modelly.couple.schedule import CouplingError

TIGHT = Solver(rtol=1e-10, atol=1e-12)
RATES = np.array([0.5, 1.0, 1.5])


class Cell(Agent):
    """One delayed variable and its rate."""

    y = Column(float, default=1.0)
    rate = Column(float, default=1.0)


def lagged(t, y, p):
    """``y'(t) = -rate y(t - 1)``."""
    return -p["rate"] * p["past"]


def exact(a, t):
    """The method-of-steps solution of ``y' = -a y(t - 1)``, ``y = 1`` before 0, for t <= 3."""
    pieces = [1.0, -a * t]
    pieces.append(a**2 * np.maximum(t - 1, 0) ** 2 / 2)
    pieces.append(-(a**3) * np.maximum(t - 2, 0) ** 3 / 6)
    return sum(pieces)


def cells(rates=RATES):
    """A model with one cell per rate."""
    model = Model(rng=1)
    for rate in rates:
        Cell(model).rate = rate
    return model


@pytest.mark.parametrize("step", [1.0, 0.5, 3.0])
def test_the_method_of_steps_gives_the_closed_form(step):
    """Whatever the model's step, chunks no longer than the delay give the exact solution."""
    model = cells()
    ode = AgentODE(model, Cell, lagged, ["y"], ["rate"], solver=TIGHT,
                   delays={"past": Delay("y", 1.0, before=1.0)})  # fmt: skip
    for start in np.arange(0.0, 3.0, step):
        ode.advance(start, step)
    np.testing.assert_allclose(model.columns[Cell].y, exact(RATES, 3.0), rtol=1e-8)


def test_a_newcomer_reads_its_own_history_and_the_past_is_pruned():
    """An agent added later starts from ``before``; passes older than the delay are dropped."""
    model = cells([1.0])
    ode = AgentODE(model, Cell, lagged, ["y"], ["rate"], solver=TIGHT,
                   delays={"past": Delay("y", 1.0, before=1.0)})  # fmt: skip
    ode.advance(0.0, 1.0)
    late = Cell(model)
    for start in (1.0, 2.0):
        ode.advance(start, 1.0)
    table = model.columns[Cell]
    np.testing.assert_allclose(
        table.y[table.agents.index(late)], exact(1.0, 2.0), rtol=1e-8
    )
    assert all(p.sol.final.max() >= 2.0 for p in ode.history.passes)


def test_a_history_function_and_removed_agents():
    """``before(t)`` is read before the first integration; a removed agent leaves no gap."""
    model = cells([1.0, 1.0])
    ode = AgentODE(model, Cell, lagged, ["y"], ["rate"], solver=TIGHT,
                   delays={"past": Delay("y", 1.0, before=np.ones_like)})  # fmt: skip
    ode.advance(0.0, 1.0)
    model.columns[Cell].agents[0].remove()
    ode.advance(1.0, 1.0)
    np.testing.assert_allclose(model.columns[Cell].y, exact(1.0, 2.0), rtol=1e-8)


def ring(t, y, p):
    """Module-level for checkpoints: ``y' = -rate y(t - 0.7)``."""
    return -p["rate"] * p["past"]


class Delayed(Model):
    """Cells with a delayed equation, saved with the model."""

    def __init__(self, rng=2):
        """Three cells."""
        super().__init__(rng=rng)
        for rate in RATES:
            Cell(self).rate = rate
        self.ode = AgentODE(self, Cell, ring, ["y"], ["rate"],
                            delays={"past": Delay("y", 0.7, before=1.0)})  # fmt: skip

    def step(self):
        """One unit of time."""
        self.ode.advance(float(self.time), 1.0)


def test_a_resumed_run_reads_the_same_past(tmp_path):
    """The history is saved: a resumed run equals a straight one bit for bit."""
    straight = Delayed()
    straight.run_for(6)
    resumed = Delayed()
    resumed.run_for(3)
    resumed.save(tmp_path / "delay.ckpt")
    loaded = Delayed.load(tmp_path / "delay.ckpt")
    loaded.run_for(3)
    np.testing.assert_array_equal(loaded.columns[Cell].y, straight.columns[Cell].y)


def test_bad_delays_are_refused():
    """A delay that is not positive, an unknown variable, a stiff method."""
    with pytest.raises(ValueError, match="positive"):
        Delay("y", 0.0)
    model = cells()
    with pytest.raises(CouplingError, match="not in the state"):
        AgentODE(model, Cell, lagged, ["y"], delays={"past": Delay("z", 1.0)})
    with pytest.raises(CouplingError, match="explicit method"):
        AgentODE(model, Cell, lagged, ["y"], solver=Solver(method="BDF"),
                 delays={"past": Delay("y", 1.0)})  # fmt: skip
    assert chunks(0.0, 2.5, 1.0) == [(0.0, 2.5 / 3), (2.5 / 3, 5 / 3), (5 / 3, 2.5)]
