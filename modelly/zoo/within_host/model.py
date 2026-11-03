"""An epidemic between hosts whose infections run as an ODE inside each host.

Each host carries the target-cell-limited model of influenza (Baccam et al., 2006): target
cells ``T``, infected cells ``I`` and virus ``V``, with

    T' = -beta T V,    I' = beta T V - delta I,    V' = p I - c V,

``beta`` drawn per host (lognormal), ``delta``, ``p`` and ``c`` shared. A host is
infectious while its virus load is above ``threshold``; the moments it rises through and
falls back through it are events located on the solver's interpolant, so the onset and the
clearance of every host are known to the instant, not rounded to the day. Between hosts, a
daily phase exposes each susceptible with probability
``1 - exp(-contacts * transmissibility * share infectious)``, seeding its virus at
``exposure_dose``.

All hosts' ODEs are integrated together with ``modelly.couple.AgentODE`` (on
``solve_batch``): every host takes the adaptive steps its own ``solve_ivp`` call would take
and is held to the same tolerance, while the right-hand side runs once per stage for the
whole population.

Validation: the integration of the whole population equals one ``solve_ivp`` call per host,
final states and event times, within the round-off of the summation order. A host with no
target cells clears its virus exponentially, ``V(t) = V0 exp(-c t)``, so its clearance time is
``log(V0 / threshold) / c`` exactly; the located event matches it to the solver's tolerance.
The ODEs keep the cells in ``[0, 1]`` and conserve ``T + I + delta * integral(I)``; the same
seed gives the same outbreak, straight or resumed from a checkpoint.

References:
    Baccam, P., Beauchemin, C., Macken, C. A., Hayden, F. G. and Perelson, A. S. (2006).
    Kinetics of influenza A virus infection in humans. Journal of Virology, 80(15),
    7590-7599.

    Hairer, E., Norsett, S. P. and Wanner, G. (1993). Solving Ordinary Differential
    Equations I: Nonstiff Problems, 2nd ed. Springer.

    Mideo, N., Alizon, S. and Day, T. (2008). Linking within- and between-host dynamics in
    the evolutionary epidemiology of infectious diseases. Trends in Ecology and Evolution,
    23(9), 511-517.
"""

from __future__ import annotations

from functools import partial
from typing import Any

import numpy as np

from modelly.core.agent import Agent
from modelly.core.columns import Column
from modelly.core.model import Model
from modelly.couple.agent_ode import AgentODE
from modelly.couple.events import ODEEvent
from modelly.couple.ode import Solver
from modelly.couple.schedule import Coupling, Phase
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario

STATE = ("cells", "infected", "virus")
DAY = 1.0


class Host(Agent):
    """A host: its infection's three state variables, its infection rate and its course."""

    cells = Column(float, default=1.0)
    infected = Column(float, default=0.0)
    virus = Column(float, default=0.0)
    beta = Column(float, default=10.0)
    exposed = Column(bool, default=False)
    infectious = Column(bool, default=False)
    onset = Column(float, default=np.nan)
    cleared = Column(float, default=np.nan)


class WithinHostScenario(Scenario):
    """Parameters of the hosts' infections and of the contacts between them.

    Attributes:
        hosts: number of hosts.
        index_cases: hosts infected at the start, with ``index_dose``.
        contacts: contacts per host per day.
        transmissibility: chance that a contact with an infectious host exposes.
        beta_median, beta_spread: the lognormal law of the infection rate (median, sigma).
        death: ``delta``, the death rate of infected cells, per day.
        production: ``p``, virions per infected cell per day (relative units).
        clearance: ``c``, the clearance rate of the virus, per day.
        threshold: the virus load above which a host is infectious.
        exposure_dose, index_dose: the virus load given at exposure and to index cases.
        rtol, atol: the integration tolerances.
        days: default run length used by ``run``.
    """

    hosts: int = 10_000
    index_cases: int = 10
    contacts: float = 8.0
    transmissibility: float = 0.1
    beta_median: float = 10.0
    beta_spread: float = 0.5
    death: float = 2.0
    production: float = 20.0
    clearance: float = 3.0
    threshold: float = 1e-2
    exposure_dose: float = 1e-6
    index_dose: float = 1e-3
    rtol: float = 1e-6
    atol: float = 1e-9
    days: int = 60


def within_host(t: Any, y: np.ndarray, p: Any, *, death, production, clearance):
    """The target-cell-limited model, for every host at once (``y`` of shape (3, hosts))."""
    cells, infected, virus = y
    infection = p["beta"] * cells * virus
    return np.array(
        [
            -infection,
            infection - death * infected,
            production * infected - clearance * virus,
        ]
    )


def above(t: Any, y: np.ndarray, p: Any, *, threshold: float) -> np.ndarray:
    """Zero when a host's virus load is at the threshold."""
    return y[2] - threshold


def becomes_infectious(table: Any, rows: np.ndarray, times: np.ndarray) -> None:
    """The hosts whose virus rose through the threshold: infectious from ``times``."""
    table["infectious"][rows] = True
    table["onset"][rows] = times


def clears(table: Any, rows: np.ndarray, times: np.ndarray) -> None:
    """The hosts whose virus fell through the threshold: no longer infectious."""
    table["infectious"][rows] = False
    table["cleared"][rows] = times


class WithinHost(Model):
    """Hosts infecting each other; each infection an ODE inside its host.

    Attributes:
        ode: the ``AgentODE`` integrating every host's infection.
        coupling: the schedule: transmission in phase 0, the hosts' ODEs in phase 1.

    Example:
        >>> model = WithinHost(WithinHostScenario(rng=1, hosts=200, days=5))
        >>> model.run()
        >>> bool(model.columns[Host].exposed.sum() >= 10)
        True
    """

    def __init__(self, scenario: WithinHostScenario = WithinHostScenario) -> None:
        """Make the hosts, their ODE and the schedule."""
        super().__init__(scenario=scenario)
        s = self.scenario
        Host.create_agents(self, s.hosts)
        table = self.columns[Host]
        table.beta[:] = self.rng.lognormal(
            np.log(s.beta_median), s.beta_spread, s.hosts
        )
        table.virus[: s.index_cases] = s.index_dose
        table.exposed[: s.index_cases] = True
        self.ode = hosts_ode(self, s)
        self.coupling = Coupling()
        self.coupling.add(Phase(self.transmit))
        self.coupling.add(self.ode, phase=1)
        self.coupling.build()
        self.datacollector = DataCollector(model_reporters=REPORTERS)
        self.datacollector.collect(self)

    def transmit(self) -> None:
        """Expose susceptible hosts with a chance set by the share infectious."""
        s, table = self.scenario, self.columns[Host]
        chance = 1.0 - np.exp(
            -s.contacts * s.transmissibility * table.infectious.mean()
        )
        new = ~table.exposed & table.draw(chance)
        table.virus[new] = s.exposure_dose
        table.exposed[new] = True

    def step(self) -> None:
        """One day: transmission, then every host's infection."""
        self.coupling.step(DAY)
        self.datacollector.collect(self)

    def run(self, days: int | None = None) -> None:
        """Run ``days`` days (the scenario's ``days`` by default)."""
        self.run_for(self.scenario.days if days is None else days)

    def attack_rate(self) -> float:
        """Share of hosts ever exposed."""
        return float(self.columns[Host].exposed.mean())


def hosts_ode(model: WithinHost, s: WithinHostScenario) -> AgentODE:
    """The ``AgentODE`` of the hosts, with the onset and clearance events."""
    rhs = partial(
        within_host, death=s.death, production=s.production, clearance=s.clearance
    )
    level = partial(above, threshold=s.threshold)
    events = [
        ODEEvent(level, direction=1, action=becomes_infectious),
        ODEEvent(level, direction=-1, action=clears),
    ]
    solver = Solver(rtol=s.rtol, atol=s.atol)
    return AgentODE(
        model, Host, rhs, list(STATE), ["beta"], events=events, solver=solver
    )


def _count(model: WithinHost, column: str) -> int:
    """Hosts for which a boolean column holds."""
    return int(np.count_nonzero(model.columns[Host][column]))


def _mean_load(model: WithinHost) -> float:
    """Mean virus load over the hosts."""
    return float(model.columns[Host].virus.mean())


REPORTERS = {
    "exposed": partial(_count, column="exposed"),
    "infectious": partial(_count, column="infectious"),
    "mean_virus": _mean_load,
}
