"""Vector-borne transmission on a landscape (Ross-Macdonald).

Hosts live on the cells of a landscape grid and move to a random neighbouring cell with
probability ``move`` per step; each is susceptible, infectious or recovered. Mosquitoes live
in the cells too, ``m`` per host on average (times a per-cell ``habitat`` suitability, a
raster of values), each susceptible, exposed (the extrinsic incubation) or infectious.
Every step a mosquito survives with probability ``survival`` and bites ``a`` times, each
time a host of its cell chosen at random. A bite of an infectious mosquito infects a
susceptible host with probability ``b``; a bite on an infectious host infects a susceptible
mosquito with probability ``c``. Exposed mosquitoes become infectious with probability
``incubation`` per step, infectious hosts recover with probability ``recovery``, and new
susceptible mosquitoes emerge so as to keep the density at ``m``.

Mosquitoes in the same cell and state are interchangeable, so they are a ``CohortTable``
with one row per (cell, state): survival, infection and incubation are binomial draws per
row. Hosts are agents with ``Column`` arrays for their state and cell row.

Validation: the Ross-Macdonald reproduction number (host to host, over one full cycle),
``R0 = m a^2 b c P / (recovery (1 - survival))``, where ``P`` is the probability that an
infected mosquito survives the incubation, is linear in the vector density ``m``
(``r0()``). Outbreaks are small when ``R0 < 1`` and their size grows with ``R0`` above
it, so the attack rates of three densities come out in the order of their ``R0``.

References:
    Ross, R. (1911). The Prevention of Malaria, 2nd ed. John Murray.

    Macdonald, G. (1957). The Epidemiology and Control of Malaria. Oxford University Press.
"""

from __future__ import annotations

from enum import IntEnum

import numpy as np

from modelly.batch.cohorts import CohortTable
from modelly.core.agent import Agent
from modelly.core.columns import Column
from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario
from modelly.space.cells.index import CellIndex
from modelly.space.grid.grids import OrthogonalVonNeumannGrid


class Host(IntEnum):
    """Host states."""

    S = 0
    I = 1  # noqa: E741 - the epidemiological name
    R = 2


class Vector(IntEnum):
    """Mosquito states."""

    S = 0
    E = 1
    I = 2  # noqa: E741 - the epidemiological name


class Person(Agent):
    """A host: its infection state and the row of its cell."""

    state = Column(np.int8)
    row = Column(np.intp)


class VectorScenario(Scenario):
    """Parameters of the vector-borne model (one step is one day).

    Attributes:
        width: landscape cells from west to east.
        height: landscape cells from south to north.
        hosts_per_cell: hosts placed in every cell at the start.
        habitat: optional per-cell suitability, shape ``(width, height)``, scaling the
            vector density (a raster's values); uniform when ``None``.
        m: mosquitoes per host.
        a: bites per mosquito per day.
        b: probability that an infectious bite infects a susceptible host.
        c: probability that a bite on an infectious host infects a mosquito.
        survival: daily survival probability of a mosquito.
        incubation: daily probability that an exposed mosquito becomes infectious.
        recovery: daily probability that an infectious host recovers.
        move: daily probability that a host moves to a neighbouring cell.
        initial_infected: infectious hosts at the start.
        steps: default run length used by ``run``.
    """

    width: int = 10
    height: int = 10
    hosts_per_cell: int = 20
    habitat: object = None
    m: float = 2.0
    a: float = 0.3
    b: float = 0.5
    c: float = 0.5
    survival: float = 0.9
    incubation: float = 0.1
    recovery: float = 0.1
    move: float = 0.3
    initial_infected: int = 10
    steps: int = 600


class VectorBorne(Model):
    """Ross-Macdonald transmission between moving hosts and mosquito cohorts per cell.

    Example:
        >>> model = VectorBorne(VectorScenario(rng=1, steps=30))
        >>> model.run()
        >>> 0.0 <= model.attack_rate() <= 1.0
        True
    """

    def __init__(self, scenario: VectorScenario = VectorScenario) -> None:
        """Place the hosts, infect a few, and fill every cell with mosquitoes."""
        super().__init__(scenario=scenario)
        s = self.scenario
        self.grid = OrthogonalVonNeumannGrid((s.width, s.height), random=self.random)
        self.index = CellIndex(self.grid)
        self.index.track(self, Person)
        cells = np.repeat(np.arange(self.index.n), s.hosts_per_cell)
        hosts = Person.create_agents(self, cells.shape[0])
        self.hosts = self.columns[Person]
        self.hosts.row = cells
        self.hosts.state[self.rng.choice(len(hosts), s.initial_infected, False)] = (
            Host.I
        )
        habitat = np.ones(self.index.n) if s.habitat is None else s.habitat
        self.capacity = s.m * s.hosts_per_cell * np.asarray(habitat, float).ravel()
        self.vectors = CohortTable(self.rng, cell=np.intp, state=np.int8)
        self.vectors.add(self.rng.poisson(self.capacity), cell=np.arange(self.index.n))
        self.datacollector = DataCollector(
            model_reporters={"S": susceptible, "I": infectious, "R": recovered}
        )
        self.datacollector.collect(self)

    def pressures(self) -> tuple[np.ndarray, np.ndarray]:
        """Daily infection hazard per cell: on a susceptible host, on a susceptible mosquito."""
        s = self.scenario
        hosts = self.index.counts(self.hosts.row)
        sick = self.index.counts(self.hosts.row, self.hosts.state == Host.I)
        v = self.vectors
        biting = np.bincount(
            v["cell"],
            weights=v["count"] * (v["state"] == Vector.I),
            minlength=len(hosts),
        )
        per_host = np.divide(1.0, hosts, out=np.zeros(len(hosts)), where=hosts > 0)
        return s.a * s.b * biting * per_host, s.a * s.c * sick * per_host

    def step(self) -> None:
        """Bites from the start-of-day state, then the mosquito life cycle, then moves."""
        s = self.scenario
        on_host, on_vector = self.pressures()
        hosts = self.hosts
        catch = self.rng.random(len(hosts)) < 1.0 - np.exp(-on_host[hosts.row])
        heal = self.rng.random(len(hosts)) < s.recovery
        sick = hosts.state == Host.I
        hosts.state[sick & heal] = Host.R
        hosts.state[(hosts.state == Host.S) & catch] = Host.I
        self.mosquito_day(on_vector)
        moving = self.rng.random(len(hosts)) < s.move
        hosts.row[moving] = self.index.random_neighbor(hosts.row[moving], self.rng)
        self.datacollector.collect(self)

    def mosquito_day(self, on_vector: np.ndarray) -> None:
        """Survive, incubate, get infected, emerge."""
        s = self.scenario
        v = self.vectors
        v.thin(s.survival)
        v.split(s.incubation, v["state"] == Vector.E, state=Vector.I)
        fresh = v["state"] == Vector.S
        v.split(1.0 - np.exp(-on_vector[v["cell"][fresh]]), fresh, state=Vector.E)
        emerging = self.rng.poisson(self.capacity * (1.0 - s.survival))
        v.add(emerging, cell=np.arange(self.index.n), state=Vector.S)
        v.merge()

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` days (the scenario's by default), or until the infection is gone."""
        for _ in range(self.scenario.steps if steps is None else steps):
            if not self.infected():
                break
            self.step()

    def infected(self) -> bool:
        """Whether any host is infectious or any mosquito exposed or infectious."""
        carrying = self.vectors["state"] != Vector.S
        return bool((self.hosts.state == Host.I).any() or self.vectors.total(carrying))

    def r0(self) -> float:
        """Ross-Macdonald R0 (host to host) for this scenario's uniform vector density."""
        s = self.scenario
        incubated = s.survival * s.incubation / (1 - s.survival * (1 - s.incubation))
        lifetime = 1.0 / (1.0 - s.survival)
        return s.m * s.a**2 * s.b * s.c * incubated * lifetime / s.recovery

    def attack_rate(self) -> float:
        """Share of hosts ever infected."""
        return float((self.hosts.state != Host.S).mean())


def susceptible(model: VectorBorne) -> int:
    """Susceptible hosts (a model reporter)."""
    return int((model.hosts.state == Host.S).sum())


def infectious(model: VectorBorne) -> int:
    """Infectious hosts (a model reporter)."""
    return int((model.hosts.state == Host.I).sum())


def recovered(model: VectorBorne) -> int:
    """Recovered hosts (a model reporter)."""
    return int((model.hosts.state == Host.R).sum())
