"""An ODE in every agent: per-agent state in columns, integrated as one batch.

``AgentODE`` advances ``dy/dt = rhs(t, y, params)`` for every agent of one class, whose
state variables and parameters are columns of ``model.columns[agent_class]``. With an
explicit method (``"RK45"``, ``"RK23"``) it calls ``solve_batch``: each agent keeps its own
step size and tolerance, as if it had its own ``solve_ivp`` call, and the right-hand side
runs once per stage for the whole population. With a stiff method (``"BDF"``, ``"Radau"``,
``"LSODA"``) it stacks the agents into one ``solve_ivp`` system and passes a block-diagonal
Jacobian sparsity, since an agent's equations involve only its own state.

Events (``modelly.couple.events.ODEEvent``) are located per agent. A terminal event stops the
agent at the crossing; after the whole population has been integrated, each event's
``action(table, rows, times)`` runs, and the stopped agents resume from their crossing to
the end of the step. Actions may change columns, not add or remove agents (do that in an
agent phase), since rows are positions in the column table.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any

import numpy as np

from modelly.couple.batch import METHODS, solve_batch
from modelly.couple.events import ODEEvent
from modelly.couple.ode import Solver
from modelly.couple.schedule import Coupling, CouplingError

STIFF = ("BDF", "Radau", "LSODA")
# A terminal event whose action leaves the state on the crossing fires again at once;
# past this many restarts in one step the step fails instead of looping.
MAX_RESTARTS = 1000


class AgentODE:
    """``dy/dt = rhs(t, y, params)`` in every agent of a class, a coupling component.

    Example:
        >>> from modelly import Agent, Model
        >>> from modelly.core.columns import Column
        >>> class Cell(Agent):
        ...     mass = Column(float, default=1.0)
        ...     rate = Column(float, default=0.5)
        ...     def __init__(self, model, rate):
        ...         super().__init__(model)
        ...         self.rate = rate
        >>> def decay(t, y, params):
        ...     return -params["rate"] * y
        >>> model = Model(rng=1)
        >>> cells = Cell.create_agents(model, 3, rate=[0.5, 1.0, 2.0])
        >>> ode = AgentODE(model, Cell, decay, state=["mass"], params=["rate"])
        >>> ode.advance(0.0, 1.0)
        >>> model.columns[Cell].mass.round(4).tolist()
        [0.6065, 0.3679, 0.1353]
    """

    def __init__(
        self,
        model: Any,
        agent_class: type,
        rhs: Callable[..., Any],
        state: Sequence[str],
        params: Sequence[str] = (),
        reads: Iterable[str] = (),
        solver: Solver | None = None,
        events: Sequence[ODEEvent] = (),
    ) -> None:
        """Integrate the columns ``state`` of ``agent_class``; ``params`` are read-only columns.

        ``reads`` are coupling quantities passed to ``rhs`` in ``params`` by name, held over
        the step. ``rhs`` and the events' functions must be module-level functions or
        methods for the model to be saved.
        """
        self.model, self.agent_class, self.rhs = model, agent_class, rhs
        self.state, self.params = tuple(state), tuple(params)
        self.reads, self.writes = tuple(reads), ()
        self.solver = solver or Solver()
        self.events = tuple(events)
        if self.solver.method not in METHODS + STIFF:
            raise CouplingError(
                f"AgentODE supports {METHODS + STIFF}, not {self.solver.method!r}"
            )
        if self.events and self.solver.method in STIFF:
            raise CouplingError(f"AgentODE events need an explicit method {METHODS}")
        self.label = f"AgentODE {getattr(rhs, '__name__', type(rhs).__name__)!r}"

    def start(self, coupling: Coupling) -> None:
        """Nothing to publish: the state lives in the agents' columns."""

    def run(self, coupling: Coupling, time: float, duration: float) -> None:
        """Read the inputs and integrate every agent over the step."""
        self.advance(time, duration, {name: coupling[name] for name in self.reads})

    def advance(
        self, time: float, duration: float, inputs: dict[str, Any] | None = None
    ) -> None:
        """Integrate every agent from ``time`` to ``time + duration``, writing the columns."""
        if self.agent_class not in self.model.columns:
            return
        table = self.model.columns[self.agent_class]
        if len(table) == 0:
            return
        params = {name: table[name] for name in self.params} | (inputs or {})
        if self.solver.method in STIFF:
            self._write(
                table, self._stacked(self._read(table), params, time, time + duration)
            )
            return
        start = np.full(len(table), float(time))
        for _ in range(MAX_RESTARTS):
            start = self._batched(table, params, start, time + duration)
            if start is None:
                return
        raise CouplingError(
            f"{self.label}: more than {MAX_RESTARTS} terminal events in a step"
        )

    def _batched(
        self, table, params, start: np.ndarray, end: float
    ) -> np.ndarray | None:
        """One ``solve_batch`` pass; the stopped agents' restart times, or None if none."""
        s = self.solver
        result = solve_batch(self.rhs, (start, end), self._read(table), params,
                             method=s.method, rtol=s.rtol, atol=s.atol, events=self.events)  # fmt: skip
        self._write(table, result.y)
        for event, log in zip(self.events, result.events):
            if event.action is not None and log.rows.size:
                event.action(table, log.rows, log.t)
        return result.t if result.stopped.any() else None

    def _stacked(self, y: np.ndarray, params: dict[str, Any], t0: float, t1: float):
        """The stiff path: every agent in one ``solve_ivp`` system, block-diagonal Jacobian."""
        from scipy import sparse  # noqa: PLC0415 - scipy is heavy
        from scipy.integrate import solve_ivp  # noqa: PLC0415

        m, k = y.shape

        def fun(t: float, flat: np.ndarray) -> np.ndarray:
            return np.asarray(
                self.rhs(np.full(k, t), flat.reshape(m, k), params), float
            ).ravel()

        s, extra = self.solver, {}
        if s.method != "LSODA":  # LSODA takes band widths, not a sparsity pattern
            extra["jac_sparsity"] = sparse.kron(np.ones((m, m)), sparse.identity(k))
        result = solve_ivp(fun, (t0, t1), y.ravel(), method=s.method, rtol=s.rtol, atol=s.atol,
                           **extra)  # fmt: skip
        if not result.success:
            raise CouplingError(f"{self.label} failed at time {t0}: {result.message}")
        return result.y[:, -1].reshape(m, k)

    def _read(self, table) -> np.ndarray:
        """The state columns as a float array of shape ``(variables, agents)``."""
        return np.array([table[name] for name in self.state], dtype=float)

    def _write(self, table, y: np.ndarray) -> None:
        """Write the state back into the columns, in place."""
        for name, values in zip(self.state, y):
            table[name][:] = values
