"""The 30-second model from the README: wealth exchange on a grid.

Run with ``python example.py``; it prints the Gini coefficient after 100 ticks.
"""

from modelly import Model
from modelly.scenarios import Scenario
from modelly.space import CellAgent, OrthogonalMooreGrid


class WealthScenario(Scenario):
    """Everything that can vary between runs lives here."""

    n: int = 120
    width: int = 12
    height: int = 12


class MoneyAgent(CellAgent):
    """An agent that wanders and hands one unit of wealth to a cellmate."""

    def __init__(self, model, cell):
        super().__init__(model)
        self.cell = cell
        self.wealth = 1

    def step(self):
        self.cell = self.cell.neighborhood.select_random_cell()
        cellmates = [a for a in self.cell.agents if a is not self]
        if self.wealth > 0 and cellmates:
            self.random.choice(cellmates).wealth += 1
            self.wealth -= 1


class WealthModel(Model):
    """A grid of money agents; inequality emerges from random exchange."""

    def __init__(self, scenario: WealthScenario = WealthScenario):
        super().__init__(scenario=scenario)
        self.grid = OrthogonalMooreGrid(
            (scenario.width, scenario.height), random=self.random
        )
        MoneyAgent.create_agents(
            self,
            scenario.n,
            self.random.choices(self.grid.all_cells.cells, k=scenario.n),
        )

    def step(self):
        self.agents.shuffle_do("step")  # every agent, in random order

    @property
    def gini(self):
        x, n = sorted(a.wealth for a in self.agents), len(self.agents)
        return (
            1 + 1 / n - 2 * sum(xi * (n - i) for i, xi in enumerate(x)) / (n * sum(x))
        )


if __name__ == "__main__":
    model = WealthModel()
    for _ in range(100):
        model.step()

    print(model.gini)  # 0.0 at t=0 ... ~0.6 after 100 ticks
