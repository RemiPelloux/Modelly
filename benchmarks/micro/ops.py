"""The core operations the performance guard times (``python -m modelly.dev perf``).

``operations()`` returns ``{name: (callable, items per call)}``; the guard times each callable
in two interpreters, the last release and this checkout, and compares nanoseconds per item.
Only public API that every 1.3 release has is used, so the same file runs in both.
"""

from __future__ import annotations

from modelly import Agent, Column, Model
from modelly._native import loops
from modelly.data.collector import DataCollector
from modelly.space import CellAgent, OrthogonalMooreGrid

AGENTS = 2000
CHURN = 500
GRID = (60, 60)
SCAN_CELLS = 200
FAR = 6  # neighbourhood radius of the wide scan
EVENTS = 500
DRAWS = 1000


class Plain(Agent):
    """An agent whose step sets one attribute."""

    def step(self):
        """One attribute write."""
        self.x = 1


class Columnar(Agent):
    """An agent with one float column."""

    wealth = Column(float, default=1.0)


class Bug(Agent):
    """An agent with three columns, created and removed in bulk."""

    age = Column(int, default=0)
    energy = Column(float, default=1.0)
    stage = Column(int, default=0)


class Walker(CellAgent):
    """A random walker on a grid."""

    def step(self):
        """Move to a random neighbouring cell."""
        self.cell = self.cell.neighborhood.select_random_cell()


def noop():
    """An event callback that does nothing."""


def agentset_ops() -> dict:
    """do, shuffle_do, select, agg and iteration over a model's agents."""
    model = Model(rng=1)
    Plain.create_agents(model, AGENTS)
    agents = model.agents
    return {
        "agentset do": (lambda: agents.do("step"), AGENTS),
        "agentset shuffle_do": (lambda: agents.shuffle_do("step"), AGENTS),
        "agentset select": (lambda: agents.select(lambda a: a.unique_id % 2), AGENTS),
        "agentset agg": (lambda: agents.agg("unique_id", sum), AGENTS),
        "agentset iterate": (lambda: list(model.agents), AGENTS),
    }


def column_ops() -> dict:
    """Column reads and writes, and creating and removing agents with columns."""
    model = Model(rng=1)
    agents = list(Columnar.create_agents(model, AGENTS))

    def read():
        total = 0.0
        for agent in agents:
            total += agent.wealth
        return total

    def write():
        for agent in agents:
            agent.wealth = 2.0

    def churn():
        fresh = Model(rng=1)
        for bug in list(Bug.create_agents(fresh, CHURN)):
            bug.remove()

    return {
        "column read": (read, AGENTS),
        "column write": (write, AGENTS),
        "column create+remove": (churn, CHURN),
    }


def lifecycle_ops() -> dict:
    """Creating and removing plain agents, events, data collection."""

    def churn():
        model = Model(rng=1)
        for agent in list(Plain.create_agents(model, CHURN)):
            agent.remove()

    def events():
        model = Model(rng=1)
        for t in range(EVENTS):
            model.schedule_event(noop, at=float(t + 1))
        model.run_until(EVENTS + 1)

    model = Model(rng=1)
    Plain.create_agents(model, AGENTS)
    collector = DataCollector(
        model_reporters={"n": lambda m: len(m.agents)},
        agent_reporters={"id": "unique_id"},
    )
    return {
        "create+remove agent": (churn, CHURN),
        "schedule+run event": (events, EVENTS),
        "datacollector collect": (lambda: collector.collect(model), AGENTS),
    }


def space_ops() -> dict:
    """Cell moves and neighbourhood walks on a torus grid."""
    model = Model(rng=1)
    grid = OrthogonalMooreGrid(GRID, torus=True, capacity=None, random=model.random)
    cells = list(grid.all_cells.cells)
    for walker, cell in zip(
        Walker.create_agents(model, AGENTS),
        model.random.choices(cells, k=AGENTS),
        strict=True,
    ):
        walker.cell = cell
    scan = cells[:SCAN_CELLS]
    return {
        "cell move": (lambda: model.agents.do("step"), AGENTS),
        "neighborhood r=1": (
            lambda: [loops.neighborhood(c, 1) for c in scan],
            SCAN_CELLS,
        ),
        "neighborhood r=6": (
            lambda: [loops.neighborhood(c, FAR) for c in scan],
            SCAN_CELLS,
        ),
    }


def random_ops() -> dict:
    """The model's generators; ``numpy control`` runs no Modelly code at all."""
    model = Model(rng=1)
    rng = model.random
    return {
        "random.random": (rng.random, 1),
        "random.randint": (lambda: rng.randint(0, 99), 1),
        "numpy control": (lambda: model.rng.random(DRAWS), 1),
    }


def operations() -> dict:
    """Every operation the guard times, by name."""
    ops = {}
    for group in (agentset_ops, column_ops, lifecycle_ops, space_ops, random_ops):
        ops.update(group())
    return ops
