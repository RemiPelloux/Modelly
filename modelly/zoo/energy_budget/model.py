"""Individual-based population with energy budgets.

Foragers walk a grid on which a resource flows in at a constant rate per cell. Every step
each forager moves to a random neighbouring cell, the foragers in a cell share its resource
equally and turn it into energy with an assimilation ``efficiency``, and each pays a
metabolic ``cost``. A forager whose energy reaches ``birth_threshold`` splits it with an
offspring in its cell; one whose energy falls below zero starves.

Validation: the energy balance. Energy is the only currency, so it regulates the
population. The resource is never capped and is eaten whenever a forager visits, so in the
long run all of it is eaten: intake equals inflow. At equilibrium the energy assimilated equals the
energy spent, ``efficiency * inflow * cells = cost * N``, which gives the carrying
capacity ``K = efficiency * inflow * cells / cost`` (``carrying_capacity()``). The only
energy leaving the balance otherwise is the deficit of starving foragers, at most one
``cost`` each, so the mean population sits at or slightly above ``K``.

The foragers keep their energy and their cell row in ``Column`` arrays and are placed by
row (``CellIndex.track``): moving, eating and starving are whole-population numpy
operations; only births create objects.

Reference:
    Grimm, V. and Railsback, S. F. (2005). Individual-based Modeling and Ecology.
    Princeton University Press.
"""

from __future__ import annotations

import numpy as np

from modelly.core.agent import Agent
from modelly.core.columns import Column
from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario
from modelly.space.cells.index import CellIndex
from modelly.space.grid.grids import OrthogonalMooreGrid


class Forager(Agent):
    """A forager: its energy and the row of the cell it stands on."""

    energy = Column(float)
    row = Column(np.intp)

    def __init__(self, model: EnergyBudget, row: int, energy: float) -> None:
        """Place the forager in cell ``row`` with ``energy``."""
        super().__init__(model)
        self.row = row
        self.energy = energy

    def reproduce(self) -> None:
        """Split the energy with an offspring in the same cell."""
        self.energy /= 2
        Forager(self.model, self.row, self.energy)


class EnergyScenario(Scenario):
    """Parameters of the energy-budget population.

    Attributes:
        width: grid cells from west to east.
        height: grid cells from south to north.
        initial: foragers at the start, on random cells.
        initial_energy: energy of each initial forager.
        inflow: resource added to every cell per step.
        efficiency: share of the eaten resource turned into energy.
        cost: energy spent by a forager per step.
        birth_threshold: energy at which a forager splits with an offspring.
        steps: default run length used by ``run``.
    """

    width: int = 30
    height: int = 30
    initial: int = 100
    initial_energy: float = 5.0
    inflow: float = 1.0
    efficiency: float = 0.5
    cost: float = 1.0
    birth_threshold: float = 10.0
    steps: int = 400


class EnergyBudget(Model):
    """Foragers that eat, pay a metabolic cost, reproduce and starve on a resource grid.

    Example:
        >>> model = EnergyBudget(EnergyScenario(rng=1, steps=50))
        >>> model.run()
        >>> model.population() > 0
        True
    """

    def __init__(self, scenario: EnergyScenario = EnergyScenario) -> None:
        """Make the grid and scatter the initial foragers."""
        super().__init__(scenario=scenario)
        s = self.scenario
        self.grid = OrthogonalMooreGrid((s.width, s.height), random=self.random)
        self.index = CellIndex(self.grid)
        self.index.track(self, Forager)
        self.resource = np.zeros(self.index.n)
        rows = self.rng.integers(0, self.index.n, s.initial)
        Forager.create_agents(self, s.initial, rows.tolist(), s.initial_energy)
        self.datacollector = DataCollector(
            model_reporters={"foragers": population, "resource": stock}
        )
        self.datacollector.collect(self)

    def step(self) -> None:
        """Move, eat, pay the cost, starve, reproduce."""
        s = self.scenario
        self.resource += s.inflow
        if self.population():
            table = self.columns[Forager]
            table.row = self.index.random_neighbor(table.row, self.rng)
            occupants = self.index.counts(table.row)
            share = self.resource[table.row] / occupants[table.row]
            self.resource[occupants > 0] = 0.0
            table.energy += s.efficiency * share - s.cost
            table.remove_where(table.energy < 0)
            table.do_where(table.energy >= s.birth_threshold, "reproduce")
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` steps (the scenario's ``steps`` by default)."""
        self.run_for(self.scenario.steps if steps is None else steps)

    def population(self) -> int:
        """The number of live foragers."""
        return len(self.columns[Forager]) if Forager in self.columns else 0

    def carrying_capacity(self) -> float:
        """``K = efficiency * inflow * cells / cost``, from the energy balance."""
        s = self.scenario
        return s.efficiency * s.inflow * self.index.n / s.cost


def population(model: EnergyBudget) -> int:
    """The number of foragers (a model reporter)."""
    return model.population()


def stock(model: EnergyBudget) -> float:
    """The uneaten resource on the grid (a model reporter)."""
    return float(model.resource.sum())
