"""Multi-scale coupling: agents with fields, ODEs and stock-flow models.

* :class:`Field`: a grid property layer that diffuses, drifts and decays on its own time
  step, conserving mass to round-off (``modelly.couple.field``);
* :class:`ODE` and :class:`StockFlow`: continuous components integrated with scipy's
  ``solve_ivp`` (``modelly.couple.ode``);
* :class:`Coupling` and :class:`Phase`: the schedule that runs them with the agents' step
  phases, checked at build time for quantities with no writer or two writers and for
  cycles inside a phase (``modelly.couple.schedule``).

See the guide in ``docs/coupling.md``::

    from modelly.couple import Coupling, Field, Phase, Transport

    coupling = Coupling()
    coupling.add(Phase(model.forage, reads=["nutrient"], writes=["uptake"]))
    coupling.add(Field(grid, "nutrient", Transport(diffusion=0.2), source="uptake"), phase=1)
    coupling.build()
    coupling.step()  # in Model.step
"""

from modelly.couple.field import Field, Transport
from modelly.couple.ode import ODE, Flow, Solver, StockFlow
from modelly.couple.schedule import Coupling, CouplingError, Phase

__all__ = [
    "ODE",
    "Coupling",
    "CouplingError",
    "Field",
    "Flow",
    "Phase",
    "Solver",
    "StockFlow",
    "Transport",
]
