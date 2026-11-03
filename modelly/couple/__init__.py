"""Multi-scale coupling: agents with fields, ODEs and stock-flow models.

* :class:`Field`: a grid property layer that diffuses, drifts and decays on its own time
  step, conserving mass to round-off (``modelly.couple.field``);
* :class:`ODE` and :class:`StockFlow`: continuous components integrated with scipy's
  ``solve_ivp`` (``modelly.couple.ode``);
* :class:`AgentODE`: an ODE in every agent, its state in columns, integrated as one batch
  with each agent's own adaptive step (``modelly.couple.agent_ode``), on
  :func:`solve_batch`, a vectorised ``solve_ivp`` for many independent systems with
  :class:`ODEEvent` zero crossings (``modelly.couple.batch``, ``modelly.couple.events``),
  inputs that vary inside a step (:class:`Forcing`, :class:`Series`) and dense output
  (:class:`BatchDense`);
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
from modelly.couple.batch import BatchResult, solve_batch
from modelly.couple.dense import BatchDense
from modelly.couple.events import EventLog, ODEEvent
from modelly.couple.field import Field, Transport
from modelly.couple.inputs import Forcing, Input, Series
from modelly.couple.ode import ODE, Flow, Solver, StockFlow
from modelly.couple.schedule import Coupling, CouplingError, Phase

__all__ = [
    "ODE",
    "AgentODE",
    "BatchDense",
    "BatchResult",
    "Coupling",
    "CouplingError",
    "EventLog",
    "Field",
    "Flow",
    "Forcing",
    "Input",
    "ODEEvent",
    "Phase",
    "Series",
    "Solver",
    "StockFlow",
    "Transport",
    "solve_batch",
]
