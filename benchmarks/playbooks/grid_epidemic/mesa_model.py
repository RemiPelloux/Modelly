"""Synchronous SIR on a torus grid, written for Mesa 2.3.

Every step: each person moves to a random Moore neighbour cell; each
susceptible then catches the infection from each infected cellmate
independently with probability ``beta`` (decided from the states at the start
of the phase); infected people recover after ``recovery`` steps.
"""

from __future__ import annotations

import mesa
from mesa.space import MultiGrid

S, I, R = 0, 1, 2


class Person(mesa.Agent):
    """One person on the grid; ``next_state`` makes the infection phase synchronous."""

    def __init__(self, unique_id, model, state):
        super().__init__(unique_id, model)
        self.state = state
        self.next_state = state
        self.days = 0

    def move(self):
        grid = self.model.grid
        cells = grid.get_neighborhood(self.pos, moore=True)
        grid.move_agent(self, self.random.choice(cells))

    def expose(self):
        if self.state == S:
            beta = self.model.beta
            for other in self.model.grid.get_cell_list_contents([self.pos]):
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

    def __init__(self, n, side, beta, recovery, initially_infected, seed):
        super().__init__(seed=seed)
        self.beta = beta
        self.recovery = recovery
        self.grid = MultiGrid(side, side, torus=True)
        for i in range(n):
            person = Person(i, self, I if i < initially_infected else S)
            pos = (self.random.randrange(side), self.random.randrange(side))
            self.grid.place_agent(person, pos)
        self.infected_history = []

    def step(self):
        agents = self.agents
        agents.shuffle(inplace=True)
        agents.do("move")
        agents.do("expose")
        agents.do("advance")
        self.infected_history.append(sum(1 for a in agents if a.state == I))


# Mesa 2.3 seeds ``model.random`` in ``Model.__new__`` from the keyword ``seed``;
# a positional seed leaves the model unseeded.
def build(seed, n, side, beta, recovery, initially_infected):
    """Build the model."""
    return Epidemic(n, side, beta, recovery, initially_infected, seed=seed)


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
