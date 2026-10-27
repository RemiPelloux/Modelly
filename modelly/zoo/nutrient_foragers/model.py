"""Foragers on a diffusing nutrient field.

A nutrient enters a closed landscape along its western edge (a river bank, say) at
``supply`` per edge cell per step, diffuses with coefficient ``diffusion`` and decays at
rate ``decay``: a ``modelly.couple.Field`` on the grid's ``nutrient`` layer, stepped on its
own stable sub-steps. Foragers walk the grid at random. Every step each moves to a random
neighbouring cell, the foragers in a cell share all of its nutrient and turn it into
energy with an assimilation ``efficiency``, and each pays a metabolic ``cost``. A forager
whose energy reaches ``birth_threshold`` splits it with an offspring; one whose energy
falls below zero starves.

The two scales are coupled by a ``Coupling``: the foragers' phase reads the field and
writes ``nutrient_input`` (the supply minus what was eaten, per cell), and the field, one
phase later, adds that input and diffuses. Nothing else changes the field, so its budget
closes exactly: the nutrient on the grid is the supply minus what was eaten and what
decayed, to round-off.

Validation: the energy balance. At equilibrium the nutrient stock is stationary, so what
the foragers eat equals what enters minus what decays, and what they assimilate equals
what they spend: ``efficiency * (supply_total - decayed) = cost * N``. Without decay this
is the carrying capacity ``K = efficiency * supply * height / cost``
(``carrying_capacity()``) however far the nutrient has to diffuse; with decay the measured
decay loss takes its share. The foragers' density falls with the distance from the river,
as the diffusing nutrient does.

References:
    Grimm, V. and Railsback, S. F. (2005). Individual-based Modeling and Ecology.
    Princeton University Press.

    Okubo, A. and Levin, S. A. (2001). Diffusion and Ecological Problems: Modern
    Perspectives, 2nd ed. Springer.
"""

from __future__ import annotations

import numpy as np

from modelly.core.agent import Agent
from modelly.core.columns import Column
from modelly.core.model import Model
from modelly.couple.field import Field, Transport
from modelly.couple.schedule import Coupling, Phase
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario
from modelly.space.cells.index import CellIndex
from modelly.space.grid.grids import OrthogonalMooreGrid

NUTRIENT, INPUT = "nutrient", "nutrient_input"
FORAGE_PHASE, FIELD_PHASE = 0, 1


class Forager(Agent):
    """A forager: its energy and the row of the cell it stands on."""

    energy = Column(float)
    row = Column(np.intp)

    def __init__(self, model: NutrientForagers, row: int, energy: float) -> None:
        """Place the forager in cell ``row`` with ``energy``."""
        super().__init__(model)
        self.row = row
        self.energy = energy

    def reproduce(self) -> None:
        """Split the energy with an offspring in the same cell."""
        self.energy /= 2
        Forager(self.model, self.row, self.energy)


class NutrientScenario(Scenario):
    """Parameters of the foragers and of the nutrient field.

    Attributes:
        width: grid cells from west to east.
        height: grid cells from south to north.
        initial: foragers at the start, on random cells.
        initial_energy: energy of each initial forager.
        supply: nutrient entering each cell of the western edge per step.
        diffusion: diffusion coefficient of the nutrient, in cells squared per step.
        decay: decay rate of the nutrient per step.
        appetite: the most nutrient a forager eats in a step.
        efficiency: share of the eaten nutrient turned into energy.
        cost: energy spent by a forager per step.
        birth_threshold: energy at which a forager splits with an offspring.
        steps: default run length used by ``run``.
    """

    width: int = 20
    height: int = 20
    initial: int = 200
    initial_energy: float = 5.0
    supply: float = 40.0
    diffusion: float = 2.0
    decay: float = 0.0
    appetite: float = 3.0
    efficiency: float = 0.5
    cost: float = 1.0
    birth_threshold: float = 10.0
    steps: int = 400


class NutrientForagers(Model):
    """Foragers that eat from a diffusing nutrient field, coupled phase by phase.

    Attributes:
        field: the nutrient ``Field`` on the grid's ``nutrient`` layer.
        eaten: nutrient eaten so far.
        deficit: energy below zero of the foragers that starved so far.

    Example:
        >>> model = NutrientForagers(NutrientScenario(rng=1, steps=50))
        >>> model.run()
        >>> model.population() > 0
        True
    """

    def __init__(self, scenario: NutrientScenario = NutrientScenario) -> None:
        """Make the grid, the field, the coupling and the initial foragers."""
        super().__init__(scenario=scenario)
        s = self.scenario
        self.grid = OrthogonalMooreGrid((s.width, s.height), random=self.random)
        self.index = CellIndex(self.grid)
        self.index.track(self, Forager)
        self.supply = np.zeros((s.width, s.height))
        self.supply[0, :] = s.supply
        self.eaten = self.deficit = 0.0
        self.coupling = self._couple()
        rows = self.rng.integers(0, self.index.n, s.initial)
        Forager.create_agents(self, s.initial, rows.tolist(), s.initial_energy)
        self.datacollector = DataCollector(
            model_reporters={
                "foragers": population,
                "nutrient": stock,
                "decayed": decayed,
            }
        )
        self.datacollector.collect(self)

    def _couple(self) -> Coupling:
        """Foragers in phase 0, the nutrient field in phase 1."""
        s = self.scenario
        coupling = Coupling()
        forage = Phase(self.forage, reads=[NUTRIENT], writes=[INPUT])
        coupling.add(forage, FORAGE_PHASE)
        transport = Transport(diffusion=s.diffusion, decay=s.decay)
        self.field = Field(self.grid, NUTRIENT, transport, source=INPUT)
        coupling.add(self.field, FIELD_PHASE)
        return coupling.build()

    def forage(self) -> None:
        """Move, eat up to the appetite, pay the cost, starve, reproduce; write the input."""
        s = self.scenario
        nutrient = self.coupling[NUTRIENT].reshape(-1)
        eaten = np.zeros_like(nutrient)
        if self.population():
            table = self.columns[Forager]
            table.row = self.index.random_neighbor(table.row, self.rng)
            occupants = self.index.counts(table.row)
            np.minimum(nutrient, s.appetite * occupants, out=eaten)
            table.energy += (
                s.efficiency * eaten[table.row] / occupants[table.row] - s.cost
            )
            self.deficit -= float(table.energy[table.energy < 0].sum())
            table.remove_where(table.energy < 0)
            table.do_where(table.energy >= s.birth_threshold, "reproduce")
        self.eaten += float(eaten.sum())
        self.coupling[INPUT] = self.supply - eaten.reshape(self.supply.shape)

    def step(self) -> None:
        """Forage, then add the input to the field and diffuse it for one step."""
        self.coupling.step()
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` steps (the scenario's ``steps`` by default)."""
        self.run_for(self.scenario.steps if steps is None else steps)

    def population(self) -> int:
        """The number of live foragers."""
        return len(self.columns[Forager]) if Forager in self.columns else 0

    def carrying_capacity(self) -> float:
        """``K = efficiency * supply * height / cost``, from the energy balance without decay."""
        s = self.scenario
        return s.efficiency * float(self.supply.sum()) / s.cost

    def density_by_column(self) -> np.ndarray:
        """Foragers per cell in each column of the grid, west to east."""
        if not self.population():
            return np.zeros(self.scenario.width)
        counts = self.index.to_layer(self.index.counts(self.columns[Forager].row))
        return counts.mean(axis=1)


def population(model: NutrientForagers) -> int:
    """The number of foragers (a model reporter)."""
    return model.population()


def stock(model: NutrientForagers) -> float:
    """The nutrient on the grid (a model reporter)."""
    return model.field.total()


def decayed(model: NutrientForagers) -> float:
    """The nutrient lost to decay so far (a model reporter)."""
    return model.field.decayed
