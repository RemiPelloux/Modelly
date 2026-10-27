"""ODE and stock-flow components, integrated with ``scipy.integrate.solve_ivp``.

An ``ODE`` holds named state variables ``y`` and a right-hand side ``rhs(t, y, inputs)``,
where ``inputs`` maps each quantity the component reads to its value at the start of the
step; inputs are held constant over the step (a zero-order hold), as an agent phase
produces them once per step. Every step integrates from ``time`` to ``time + duration``
with the adaptive Runge-Kutta (or implicit) method and tolerances of its ``Solver``, then
publishes each state variable under its name. The integration starts afresh every step from
the stored state, so a run is a deterministic function of the state and the inputs, and a
checkpointed model resumes bit for bit.

A ``StockFlow`` is the system-dynamics form: stocks, and flows that move material from one
stock to another or across the model boundary (``None``), at a rate computed from the
stocks and the inputs. Its equations are ``d stock / dt = inflows - outflows``, and it also
integrates the amount moved by each flow (``totals``). Runge-Kutta methods keep linear
invariants exactly, so ``sum(stocks) - sum(stocks at start)`` equals the net amount moved in
across the boundary to round-off: a mass balance that holds whatever the tolerances.

References:
    Dormand, J. R. and Prince, P. J. (1980). A family of embedded Runge-Kutta formulae.
    Journal of Computational and Applied Mathematics, 6(1), 19-26.

    Sterman, J. D. (2000). Business Dynamics: Systems Thinking and Modeling for a Complex
    World. Irwin/McGraw-Hill.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from modelly.couple.schedule import CouplingError

if TYPE_CHECKING:
    from modelly.couple.schedule import Coupling

DEFAULT_RTOL = 1e-8
DEFAULT_ATOL = 1e-10


@dataclass(frozen=True)
class Solver:
    """How ``solve_ivp`` integrates a step.

    Attributes:
        method: a ``solve_ivp`` method: ``"RK45"`` (Dormand-Prince), ``"DOP853"``,
            ``"Radau"``, ``"BDF"`` or ``"LSODA"`` for stiff systems.
        rtol: the relative tolerance.
        atol: the absolute tolerance.
    """

    method: str = "RK45"
    rtol: float = DEFAULT_RTOL
    atol: float = DEFAULT_ATOL


class ODE:
    """Named state variables advanced by ``dy/dt = rhs(t, y, inputs)``, a coupling component.

    Attributes:
        y: the state, in the order of the ``initial`` mapping.
        names: the state variables, also the quantities the component writes.

    Example:
        >>> def decay(t, y, inputs):
        ...     return -0.5 * y
        >>> ode = ODE(decay, {"amount": 1.0})
        >>> ode.advance(0.0, 2.0)
        >>> round(ode.state["amount"], 6)
        0.367879
    """

    def __init__(
        self,
        rhs: Callable[[float, np.ndarray, dict[str, Any]], Any],
        initial: dict[str, float],
        reads: Iterable[str] = (),
        solver: Solver | None = None,
    ) -> None:
        """Start at ``initial``; ``rhs`` must be a module-level function or a method to be saved."""
        self.rhs = rhs
        self.names = tuple(initial)
        self.y = np.array([float(initial[name]) for name in self.names])
        self.reads = tuple(reads)
        self.writes = self.names
        self.solver = solver or Solver()
        self.label = f"ODE {getattr(rhs, '__name__', type(rhs).__name__)!r}"

    @property
    def state(self) -> dict[str, float]:
        """The state variables by name."""
        return dict(zip(self.names, self.y.tolist()))

    def derivative(self, t: float, y: np.ndarray, inputs: dict[str, Any]) -> np.ndarray:
        """``dy/dt`` at ``(t, y)``, as ``solve_ivp`` calls it."""
        return np.asarray(self.rhs(t, y, inputs), dtype=float)

    def advance(
        self, time: float, duration: float, inputs: dict[str, Any] | None = None
    ) -> None:
        """Integrate from ``time`` to ``time + duration`` with ``inputs`` held constant.

        Raises:
            CouplingError: if the integrator fails (``solve_ivp``'s message is included).
        """
        from scipy.integrate import solve_ivp  # noqa: PLC0415 - scipy is heavy

        s = self.solver
        result = solve_ivp(
            self.derivative,
            (time, time + duration),
            self.y,
            method=s.method,
            rtol=s.rtol,
            atol=s.atol,
            args=(inputs or {},),
        )
        if not result.success:
            raise CouplingError(f"{self.label} failed at time {time}: {result.message}")
        self.y = result.y[:, -1].copy()

    def start(self, coupling: Coupling) -> None:
        """Publish the initial state."""
        coupling.values.update(zip(self.writes, self.y.tolist()))

    def run(self, coupling: Coupling, time: float, duration: float) -> None:
        """Read the inputs, integrate the step, publish the state."""
        self.advance(time, duration, {name: coupling[name] for name in self.reads})
        for name, value in zip(self.writes, self.y.tolist()):
            coupling[name] = value


@dataclass(frozen=True)
class Flow:
    """A flow of a stock-flow model.

    Attributes:
        name: the flow's name, the key of its total in ``StockFlow.totals``.
        rate: ``rate(stocks, inputs)``, the amount per unit time; a module-level function.
        source: the stock it drains, or ``None`` for the outside.
        target: the stock it fills, or ``None`` for the outside.
    """

    name: str
    rate: Callable[[dict[str, float], dict[str, Any]], float]
    source: str | None = None
    target: str | None = None


class StockFlow(ODE):
    """Stocks joined by flows (system dynamics), a coupling component.

    The state is the stocks followed by the running total of every flow; only the stocks
    are published to the coupling.
    """

    def __init__(
        self,
        stocks: dict[str, float],
        flows: Sequence[Flow],
        reads: Iterable[str] = (),
        solver: Solver | None = None,
    ) -> None:
        """Start the stocks at the given values and every flow total at zero."""
        initial = dict(stocks) | {_total(f.name): 0.0 for f in flows}
        if len(initial) != len(stocks) + len(flows):
            raise CouplingError(
                "Flow names must be unique and differ from the stock names."
            )
        super().__init__(_no_rhs, initial, reads, solver)
        self.flows = tuple(flows)
        self.stocks = tuple(stocks)
        self.writes = self.stocks
        self.label = f"StockFlow({', '.join(self.stocks)})"
        self.incidence = _incidence(self.stocks, self.flows)

    @property
    def totals(self) -> dict[str, float]:
        """The amount moved by each flow since the start."""
        return dict(
            zip((f.name for f in self.flows), self.y[len(self.stocks) :].tolist())
        )

    def derivative(self, t: float, y: np.ndarray, inputs: dict[str, Any]) -> np.ndarray:
        """The stocks' net flows followed by the flow rates."""
        stocks = dict(zip(self.stocks, y[: len(self.stocks)].tolist()))
        rates = np.array([float(flow.rate(stocks, inputs)) for flow in self.flows])
        return np.concatenate((self.incidence @ rates, rates))


def _incidence(stocks: tuple[str, ...], flows: tuple[Flow, ...]) -> np.ndarray:
    """The stock-by-flow matrix: -1 where a flow drains a stock, +1 where it fills one.

    Raises:
        CouplingError: if a flow names a stock that does not exist.
    """
    position = {name: i for i, name in enumerate(stocks)}
    unknown = [
        f.name
        for f in flows
        for end in (f.source, f.target)
        if end is not None and end not in position
    ]
    if unknown:
        raise CouplingError(
            f"Flows {unknown} name a stock that is not in {list(stocks)}."
        )
    incidence = np.zeros((len(stocks), len(flows)))
    for j, flow in enumerate(flows):
        if flow.source is not None:
            incidence[position[flow.source], j] -= 1.0
        if flow.target is not None:
            incidence[position[flow.target], j] += 1.0
    return incidence


def _total(name: str) -> str:
    """The state-variable name of a flow's running total."""
    return f"{name}:total"


def _no_rhs(t: float, y: np.ndarray, inputs: dict[str, Any]) -> np.ndarray:
    """Placeholder right-hand side: a ``StockFlow`` computes its own derivative."""
    raise NotImplementedError  # pragma: no cover
