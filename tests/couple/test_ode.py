"""ODE and stock-flow components against closed forms and their own mass balance."""

import numpy as np
import pytest

from modelly.couple.ode import ODE, Flow, Solver, StockFlow
from modelly.couple.schedule import Coupling, CouplingError, Phase

GROWTH, CAPACITY = 0.8, 50.0
# The default tolerances (rtol 1e-8) leave a global error well under 1e-6.
CLOSED_FORM = 1e-6
ROUND_OFF = 1e-12


def logistic(t, y, inputs):
    """``y' = r y (1 - y / K)``."""
    return GROWTH * y * (1 - y / CAPACITY)


def driven(t, y, inputs):
    """``y' = inflow - y / tau``, the inflow read from the coupling."""
    return inputs["inflow"] - y / 4.0


def blow_up(t, y, inputs):
    """``y' = y**2``, infinite at ``t = 1 / y0``."""
    return y**2


def inflow_rate(stocks, inputs):
    """The inflow quantity, per unit time."""
    return inputs["inflow"]


def transfer_rate(stocks, inputs):
    """A first-order transfer from ``a`` to ``b``."""
    return 0.3 * stocks["a"]


def loss_rate(stocks, inputs):
    """A first-order loss of ``b`` to the outside."""
    return 0.1 * stocks["b"]


def chain(reads=("inflow",)):
    """Outside -> a -> b -> outside."""
    flows = [
        Flow("in", inflow_rate, target="a"),
        Flow("transfer", transfer_rate, source="a", target="b"),
        Flow("loss", loss_rate, source="b"),
    ]
    return StockFlow({"a": 1.0, "b": 0.0}, flows, reads=reads)


@pytest.mark.parametrize("method", ["RK45", "DOP853", "Radau", "LSODA"])
def test_logistic_growth_matches_its_closed_form(method):
    """``y = K / (1 + (K / y0 - 1) exp(-r t))``, step after step, for each method."""
    ode = ODE(logistic, {"n": 1.0}, solver=Solver(method=method))
    for step in range(10):
        ode.advance(float(step), 1.0)
        t = step + 1.0
        exact = CAPACITY / (1 + (CAPACITY - 1.0) * np.exp(-GROWTH * t))
        assert ode.state["n"] == pytest.approx(exact, rel=CLOSED_FORM)


def test_inputs_are_held_over_the_step():
    """With inflow ``a`` held for a step, ``y(1) = y0 e^{-1/tau} + a tau (1 - e^{-1/tau})``."""
    coupling = Coupling()
    coupling.add(Phase(int, writes=("inflow",), initial={"inflow": 3.0}))
    ode = coupling.add(ODE(driven, {"y": 2.0}, reads=("inflow",)), phase=1)
    coupling.build()
    assert coupling["y"] == 2.0  # the initial state is published at build
    coupling.step()
    decay = np.exp(-1 / 4.0)
    assert coupling["y"] == pytest.approx(
        2.0 * decay + 3.0 * 4.0 * (1 - decay), rel=CLOSED_FORM
    )
    assert coupling["y"] == ode.state["y"]
    assert coupling.time == 1.0


def test_a_failing_integration_raises():
    """A solution that blows up inside the step is reported with the solver's message."""
    ode = ODE(blow_up, {"y": 1.0})
    with pytest.raises(CouplingError, match="blow_up"):
        ode.advance(0.0, 2.0)


def test_stock_flow_balances_to_round_off():
    """Stocks change by exactly the net flow across the boundary, flow totals included."""
    model = chain()
    start = sum(model.state[s] for s in model.stocks)
    for step in range(20):
        model.advance(float(step), 1.0, {"inflow": 0.5 * step})
    totals = model.totals
    stocks = model.y[: len(model.stocks)]
    assert stocks.sum() == pytest.approx(
        start + totals["in"] - totals["loss"], rel=ROUND_OFF
    )
    assert stocks[0] == pytest.approx(
        1.0 + totals["in"] - totals["transfer"], rel=ROUND_OFF
    )
    assert totals["in"] == pytest.approx(0.5 * sum(range(20)), rel=ROUND_OFF)


def test_stock_flow_publishes_only_the_stocks():
    """The coupling sees ``a`` and ``b``; the flow totals stay on the component."""
    coupling = Coupling()
    coupling.add(Phase(int, writes=("inflow",), initial={"inflow": 1.0}))
    model = coupling.add(chain(), phase=1)
    coupling.build()
    coupling.step()
    assert model.writes == ("a", "b")
    assert set(coupling.values) == {"inflow", "a", "b"}
    assert model.label == "StockFlow(a, b)"


def test_stock_flow_refuses_unknown_stocks_and_clashing_names():
    """A flow must join known stocks, and names must not collide."""
    with pytest.raises(CouplingError, match="not in"):
        StockFlow({"a": 1.0}, [Flow("leak", loss_rate, source="c")])
    with pytest.raises(CouplingError, match="unique"):
        StockFlow({"a": 1.0}, [Flow("x", loss_rate), Flow("x", loss_rate)])
