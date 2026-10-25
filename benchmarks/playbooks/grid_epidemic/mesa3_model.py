"""Synchronous SIR on a torus grid, written for Mesa 3.5.

Every step: each person moves to a random Moore neighbour cell; each
susceptible then catches the infection from each infected cellmate
independently with probability ``beta`` (decided from the states at the start
of the phase); infected people recover after ``recovery`` steps. People are
``CellAgent`` objects on an ``OrthogonalMooreGrid``; the three phases are
``shuffle_do("move")``, ``do("expose")`` and ``do("advance")``.
"""

from __future__ import annotations

import mesa
from mesa.discrete_space import CellAgent, OrthogonalMooreGrid

S, I, R = 0, 1, 2


class Person(CellAgent):
    """One person on the grid; ``next_state`` makes the infection phase synchronous."""

    def __init__(self, model, state, cell):
        super().__init__(model)
        self.state = state
        self.next_state = state
        self.days = 0
        self.cell = cell

    def move(self):
        self.cell = self.cell.neighborhood.select_random_cell()

    def expose(self):
        if self.state == S:
            beta = self.model.beta
            for other in self.cell.agents:
                if other.state == I and self.random.random() < beta:
                    self.next_state = I
                    break
        elif self.state == I:
            self.days += 1
            if self.days >= self.model.recovery:
                self.next_state = R

    def advance(self):
        self.state = self.next_state


class Epidemic(mesa.Model):
    """The grid, the people and the three-phase step."""

    def __init__(self, n, side, beta, recovery, initially_infected, rng):
        super().__init__(rng=rng)
        self.beta = beta
        self.recovery = recovery
        self.grid = OrthogonalMooreGrid((side, side), torus=True, random=self.random)
        Person.create_agents(
            self,
            n,
            state=[I if i < initially_infected else S for i in range(n)],
            cell=self.random.choices(self.grid.all_cells.cells, k=n),
        )
        self.infected_history = []

    def step(self):
        self.agents.shuffle_do("move")
        self.agents.do("expose")
        self.agents.do("advance")
        self.infected_history.append(sum(1 for a in self.agents if a.state == I))


def build(seed, n, side, beta, recovery, initially_infected):
    """Build the model."""
    return Epidemic(n, side, beta, recovery, initially_infected, rng=seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    for _ in range(steps):
        model.step()
    history = model.infected_history
    states = [a.state for a in model.agents]
    peak = max(history)
    return {
        "population": len(states),
        "stats": {
            "final_S": states.count(S),
            "final_I": states.count(I),
            "final_R": states.count(R),
            "peak_I": peak,
            "peak_step": history.index(peak) + 1,
            "mean_I": sum(history) / len(history),
        },
    }
