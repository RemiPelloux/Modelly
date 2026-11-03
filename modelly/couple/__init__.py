"""Multi-scale coupling: agents with fields, ODEs and stock-flow models.

* :class:`Field`: a grid property layer that diffuses, drifts and decays on its own time
  step, conserving mass to round-off (``modelly.couple.field``);
* :class:`ODE` and :class:`StockFlow`: continuous components integrated with scipy's
  ``solve_ivp`` (``modelly.couple.ode``);
* :class:`AgentODE`: an ODE in every agent, its state in columns, integrated as one batch
  with each agent's own adaptive step (``modelly.couple.agent_ode``), on
  :func:`solve_batch`, a vectorised ``solve_ivp`` for many independent systems with
  :class:`ODEEvent` zero crossings (``modelly.couple.batch``, ``modelly.couple.events``),
  inputs that vary inside a step (:class:`Forcing`, :class:`Series`), dense output
  (:class:`BatchDense`) and delays (:class:`Delay`, ``modelly.couple.delay``);
* :class:`AgentSDE` and :func:`solve_sde_batch`: stochastic equations per agent,
  Euler-Maruyama or Milstein, noise from the model's seed (``modelly.couple.sde``);
* :class:`Companion` and :class:`MeanField`: an agent model's ODE limit run next to it,
  and the gap between them (``modelly.couple.meanfield``);
* :class:`Coupling` and :class:`Phase`: the schedule that runs them with the agents' step
  phases, checked at build time for quantities with no writer or two writers and for
  cycles inside a phase (``modelly.couple.schedule``).

See the guides in ``docs/coupling.md`` and ``docs/agent_odes.md``::

    from modelly.couple import Coupling, Field, Phase, Transport

    coupling = Coupling()
    coupling.add(Phase(model.forage, reads=["nutrient"], writes=["uptake"]))
    coupling.add(Field(grid, "nutrient", Transport(diffusion=0.2), source="uptake"), phase=1)
    coupling.build()
    coupling.step()  # in Model.step
"""

from modelly.couple.agent_ode import AgentODE
from modelly.couple.agent_sde import AgentSDE
from modelly.couple.batch import BatchResult, solve_batch
from modelly.couple.delay import Delay
from modelly.couple.dense import BatchDense
from modelly.couple.events import EventLog, ODEEvent
from modelly.couple.field import Field, Transport
from modelly.couple.inputs import Forcing, Input, Series
from modelly.couple.meanfield import Companion, MeanField, gap_by_size
from modelly.couple.ode import ODE, Flow, Solver, StockFlow
from modelly.couple.schedule import Coupling, CouplingError, Phase
from modelly.couple.sde import SDEResult, solve_sde_batch

__all__ = [
    "ODE",
    "AgentODE",
    "AgentSDE",
    "BatchDense",
    "BatchResult",
    "Companion",
    "Coupling",
    "CouplingError",
    "Delay",
    "EventLog",
    "Field",
    "Flow",
    "Forcing",
    "Input",
    "MeanField",
    "ODEEvent",
    "Phase",
    "SDEResult",
    "Series",
    "Solver",
    "StockFlow",
    "Transport",
    "gap_by_size",
    "solve_batch",
    "solve_sde_batch",
]
