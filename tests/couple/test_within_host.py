"""The guide's worked example (docs/agent_odes.md): an epidemic whose hosts carry viral ODEs."""

import numpy as np

from modelly import Agent, Model
from modelly.core.columns import Column
from modelly.couple import AgentODE, Coupling, Event, Phase, Solver

THRESHOLD = 1e-2  # virus load above which a host is infectious


class Host(Agent):
    """A host whose infection runs as three ODEs, its state in columns."""

    cells = Column(float, default=1.0)
    infected = Column(float, default=0.0)
    virus = Column(float, default=0.0)
    beta = Column(float, default=10.0)
    infectious = Column(bool, default=False)
    onset = Column(float, default=np.nan)


def within_host(t, y, p):
    """Baccam et al. (2006): target cells, infected cells and virus in each host."""
    cells, infected, virus = y
    infection = p["beta"] * cells * virus
    return np.array(
        [-infection, infection - 2.0 * infected, 20.0 * infected - 3.0 * virus]
    )


def above(t, y, p):
    """Zero when the virus load is at the threshold."""
    return y[2] - THRESHOLD


def becomes_infectious(table, rows, times):
    """Mark the hosts whose virus rose through the threshold, and when."""
    table["infectious"][rows] = True
    table["onset"][rows] = times


def recovers(table, rows, times):
    """Unmark the hosts whose virus fell through it."""
    table["infectious"][rows] = False


class Outbreak(Model):
    """Hosts infect each other in proportion to the infectious share; each infection is an ODE."""

    def __init__(self, hosts=2_000, contacts=8.0, rng=42):
        """Ten index cases among ``hosts``, infection rates drawn per host."""
        super().__init__(rng=rng)
        Host.create_agents(self, hosts)
        self.table = self.columns[Host]
        self.table.beta[:] = self.rng.lognormal(np.log(10.0), 0.5, hosts)
        self.table.virus[:10] = 1e-3
        self.contacts = contacts
        events = [
            Event(above, direction=1, action=becomes_infectious),
            Event(above, direction=-1, action=recovers),
        ]
        self.coupling = Coupling()
        self.coupling.add(Phase(self.transmit))
        ode = AgentODE(self, Host, within_host, state=["cells", "infected", "virus"],
                       params=["beta"], events=events, solver=Solver(rtol=1e-6, atol=1e-9))  # fmt: skip
        self.coupling.add(ode, phase=1)
        self.coupling.build()

    def transmit(self):
        """Expose susceptible hosts with a chance set by the infectious share."""
        table = self.table
        susceptible = table.virus == 0.0
        exposed = susceptible & table.draw(
            1 - np.exp(-self.contacts * table.infectious.mean() * 0.1)
        )
        table.virus[exposed] = 1e-6

    def step(self):
        """One day."""
        self.coupling.step(1.0)


def test_the_outbreak_spreads_and_stays_within_tolerance_of_positive():
    """Most hosts are infected, after day 0; no state falls below zero by more than ``atol``."""
    model = Outbreak()
    model.run_for(40)
    table = model.columns[Host]
    onset = table.onset[np.isfinite(table.onset)]
    assert onset.size > len(table) // 2
    assert onset.min() > 0.0
    assert min(table.cells.min(), table.virus.min()) > -1e-9


def test_the_same_seed_gives_the_same_outbreak():
    """Two runs with one seed agree bit for bit."""
    first, second = Outbreak(hosts=500), Outbreak(hosts=500)
    first.run_for(20)
    second.run_for(20)
    for name in ("cells", "infected", "virus", "onset"):
        np.testing.assert_array_equal(
            first.columns[Host][name], second.columns[Host][name]
        )
