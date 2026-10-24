"""Boltzmann wealth exchange, written for Mesa 2.3.

Everyone starts with ``initial_wealth`` coins. Every step the agents act one
at a time in a random order (``RandomActivation``); an agent with at least one
coin gives one to a uniformly random agent (possibly itself). A
``DataCollector`` records the Gini coefficient of wealth and every agent's
wealth after each step. The partner is drawn from a list the model keeps,
because indexing an ``AgentSet`` in Mesa 2.3 copies its keys (O(n) per draw).
"""

from __future__ import annotations

import mesa


class Person(mesa.Agent):
    """Holds coins and gives one away per step if it has any."""

    def __init__(self, unique_id, model, wealth):
        super().__init__(unique_id, model)
        self.wealth = wealth

    def step(self):
        if self.wealth > 0:
            other = self.random.choice(self.model.people)
            other.wealth += 1
            self.wealth -= 1


def gini(model):
    """Gini coefficient of the agents' wealth."""
    x = sorted(agent.wealth for agent in model.people)
    n = len(x)
    b = sum(xi * (n - i) for i, xi in enumerate(x)) / (n * sum(x))
    return 1 + 1 / n - 2 * b


class Economy(mesa.Model):
    """The agents, the scheduler and the data collector."""

    def __init__(self, n, initial_wealth, seed):
        super().__init__(seed=seed)
        self.schedule = mesa.time.RandomActivation(self)
        self.people = [Person(i, self, initial_wealth) for i in range(n)]
        for person in self.people:
            self.schedule.add(person)
        self.datacollector = mesa.DataCollector(
            model_reporters={"gini": gini}, agent_reporters={"wealth": "wealth"}
        )

    def step(self):
        self.schedule.step()
        self.datacollector.collect(self)


# Mesa 2.3 seeds ``model.random`` in ``Model.__new__`` from the keyword ``seed``;
# a positional seed leaves the model unseeded.
def build(seed, n, initial_wealth):
    """Build the model."""
    return Economy(n, initial_wealth, seed=seed)


def simulate(model, steps):
    """Run ``steps`` steps and summarise."""
    for _ in range(steps):
        model.step()
    history = model.datacollector.model_vars["gini"]
    wealth = [person.wealth for person in model.people]
    return {
        "population": len(wealth),
        "stats": {
            "final_gini": history[-1],
            "mean_gini": sum(history) / len(history),
            "final_zero_share": wealth.count(0) / len(wealth),
            "final_max_wealth": max(wealth),
        },
    }
