"""A stochastic differential equation in every agent, its noise from the model's seed.

``AgentSDE`` advances ``dy = drift dt + diffusion dW`` for every agent of a class, the state
variables and parameters being columns, with ``solve_sde_batch`` on a fixed sub-step ``dt``.
The Wiener increments come from ``model.rng``, so a run is a function of its seed, and a
checkpoint, which saves the generator's state, resumes the same noise: a resumed run equals a
straight one bit for bit. Agents added or removed between steps are followed, as for
``AgentODE``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

import numpy as np

from modelly.couple.inputs import Input
from modelly.couple.schedule import Coupling, CouplingError
from modelly.couple.sde import SCHEMES, solve_sde_batch


class AgentSDE:
    """``dy = drift(t, y, p) dt + diffusion(t, y, p) dW`` in every agent of a class.

    Example:
        >>> from modelly import Agent, Model
        >>> from modelly.core.columns import Column
        >>> class Firm(Agent):
        ...     capital = Column(float, default=1.0)
        >>> def growth(t, y, p):
        ...     return 0.05 * y
        >>> def shocks(t, y, p):
        ...     return 0.2 * y
        >>> model = Model(rng=1)
        >>> firms = Firm.create_agents(model, 3)
        >>> AgentSDE(model, Firm, growth, shocks, state=["capital"], dt=0.01).advance(0.0, 1.0)
        >>> bool((model.columns[Firm].capital > 0).all())
        True
    """

    def __init__(
        self,
        model: Any,
        agent_class: type,
        drift: Callable[..., Any],
        diffusion: Callable[..., Any],
        state: Sequence[str],
        params: Sequence[str] = (),
        *,
        dt: float,
        scheme: str = "euler",
        reads: Iterable[str] = (),
        forcings: Mapping[str, Input] | None = None,
    ) -> None:
        """Integrate the columns ``state`` of ``agent_class`` on the sub-step ``dt``.

        ``params`` are read-only columns, ``reads`` coupling quantities held over the step,
        ``forcings`` inputs read at each sub-step's time. The functions must be module-level
        functions or methods for the model to be saved.
        """
        if scheme not in SCHEMES:
            raise CouplingError(f"AgentSDE supports {SCHEMES}, not {scheme!r}")
        if dt <= 0:
            raise CouplingError(f"AgentSDE needs a positive dt, not {dt}")
        self.model, self.agent_class = model, agent_class
        self.drift, self.diffusion = drift, diffusion
        self.state, self.params = tuple(state), tuple(params)
        self.dt, self.scheme = float(dt), scheme
        self.reads, self.writes = tuple(reads), ()
        self.forcings = dict(forcings or {})
        self.label = f"AgentSDE {getattr(drift, '__name__', type(drift).__name__)!r}"

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
        params = {name: table[name] for name in self.params} | self.forcings
        params |= inputs or {}
        y = np.array([table[name] for name in self.state], dtype=float)
        result = solve_sde_batch(self.drift, self.diffusion, (time, time + duration), y,
                                 params, dt=self.dt, rng=self.model.rng, scheme=self.scheme)  # fmt: skip
        for name, values in zip(self.state, result.y):
            table[name][:] = values
