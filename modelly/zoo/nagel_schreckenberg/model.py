"""Nagel-Schreckenberg traffic on a ring road.

A single-lane ring road of ``length`` cells, each holding at most one car. Every step, all
cars update in parallel:

1. accelerate: ``v = min(v + 1, max_speed)``;
2. brake to the gap: ``v = min(v, gap)``, the number of empty cells to the car ahead;
3. dawdle: with probability ``dawdle``, ``v = max(v - 1, 0)``;
4. move ``v`` cells forward.

Cars are ``Car`` agents whose ``position`` and ``velocity`` are ``Column`` attributes, so
the whole road updates with a handful of numpy operations on the column table. Cars never
overtake, so the rows stay in road order (cyclically) and the car ahead of row ``i`` is row
``i + 1``.

Validation: the fundamental diagram, flow ``J = density * mean speed`` against density.
Without dawdling the steady-state flow is exactly ``min(density * max_speed, 1 - density)``:
free flow below the critical density ``1 / (max_speed + 1)``, a jam moving backwards above
it. With dawdling the flow rises with density, peaks at an interior density and falls; at
low density every car runs at ``max_speed - 1`` with probability ``dawdle`` and at
``max_speed`` otherwise, so ``J = density * (max_speed - dawdle)``.

References:
    Nagel, K. and Schreckenberg, M. (1992). A cellular automaton model for freeway
    traffic. Journal de Physique I, 2(12), 2221-2229.
"""

from __future__ import annotations

import numpy as np

from modelly.core.agent import Agent
from modelly.core.columns import Column
from modelly.core.model import Model
from modelly.data.collector import DataCollector
from modelly.scenarios.scenario import Scenario


class TrafficScenario(Scenario):
    """Parameters of the Nagel-Schreckenberg model.

    Attributes:
        length: number of cells of the ring road.
        density: share of cells holding a car.
        max_speed: the speed limit, in cells per step.
        dawdle: probability per step that a car slows down by one for no reason.
        steps: default run length used by ``run``.
    """

    length: int = 1000
    density: float = 0.15
    max_speed: int = 5
    dawdle: float = 0.25
    steps: int = 500


class Car(Agent):
    """A car: its cell on the ring and its speed, both stored in columns."""

    position = Column(np.int64)
    velocity = Column(np.int64)


class NagelSchreckenberg(Model):
    """Cars on a ring road, updated in parallel on their column table.

    Example:
        >>> model = NagelSchreckenberg(TrafficScenario(rng=1, steps=20))
        >>> model.run()
        >>> len(model.cars) == round(0.15 * 1000)
        True
    """

    def __init__(self, scenario: TrafficScenario = TrafficScenario) -> None:
        """Place the cars on distinct random cells, standing still."""
        super().__init__(scenario=scenario)
        s = self.scenario
        n = round(s.density * s.length)
        if not 0 < n <= s.length:
            raise ValueError(
                f"density {s.density} gives {n} cars on {s.length} cells; "
                "need at least one car and at most one per cell"
            )
        Car.create_agents(self, n)
        self.cars = self.columns[Car]
        cells = self.rng.choice(s.length, size=n, replace=False)
        self.cars.position = np.sort(cells)
        self.datacollector = DataCollector(
            model_reporters={"flow": "flow", "mean_speed": "mean_speed"}
        )
        self.datacollector.collect(self)

    def gaps(self) -> np.ndarray:
        """Empty cells between every car and the car ahead of it."""
        position = self.cars.position
        ahead = np.roll(position, -1)
        return (ahead - position - 1) % self.scenario.length

    def step(self) -> None:
        """Accelerate, brake to the gap, dawdle, move: all cars at once."""
        s = self.scenario
        cars = self.cars
        speed = np.minimum(cars.velocity + 1, s.max_speed)
        speed = np.minimum(speed, self.gaps())
        slow = self.rng.random(speed.shape[0]) < s.dawdle
        speed = np.maximum(speed - slow, 0)
        cars.velocity = speed
        cars.position = (cars.position + speed) % s.length
        self.datacollector.collect(self)

    def run(self, steps: int | None = None) -> None:
        """Run ``steps`` steps (the scenario's ``steps`` by default)."""
        self.run_for(self.scenario.steps if steps is None else steps)

    @property
    def mean_speed(self) -> float:
        """Mean speed of the cars, in cells per step."""
        return float(self.cars.velocity.mean())

    @property
    def flow(self) -> float:
        """Cars passing a point per step: density times mean speed."""
        return float(self.cars.velocity.sum() / self.scenario.length)


def fundamental_diagram(densities, transient: int, measured: int, **params) -> list:
    """Mean flow after ``transient`` steps, over ``measured`` steps, at each density.

    ``params`` are the other ``TrafficScenario`` parameters (``rng``, ``dawdle``...).

    Example:
        >>> flows = fundamental_diagram([0.1, 0.5], 50, 50, rng=1, dawdle=0.0)
        >>> [round(f, 2) for f in flows]
        [0.5, 0.5]
    """
    flows = []
    for density in densities:
        model = NagelSchreckenberg(TrafficScenario(density=density, **params))
        model.run(transient)
        total = 0.0
        for _ in range(measured):
            model.step()
            total += model.flow
        flows.append(total / measured)
    return flows
