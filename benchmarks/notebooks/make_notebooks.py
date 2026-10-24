"""Generate the benchmark notebooks in this directory.

Each notebook defines a workload, runs it at three sizes, prints one line per
size as ``RESULT {json}`` (the runner collects those) and shows a table. Edit
the ``WORKLOADS`` below and run ``python benchmarks/notebooks/make_notebooks.py``
to regenerate; never edit the ``.ipynb`` files by hand.
"""

from __future__ import annotations

from pathlib import Path

import nbformat

HERE = Path(__file__).resolve().parent

HELPER = '''
import json
import time

import pandas as pd


def bench(label, make_model, steps, agents_of=lambda m: len(m.agents)):
    """Build the model, time ``steps`` steps, print a RESULT line, return a row."""
    model = make_model()
    n = agents_of(model)
    t0 = time.perf_counter()
    model.run_for(steps)
    per_step = (time.perf_counter() - t0) / steps
    row = {
        "label": label,
        "agents": n,
        "ms_per_step": round(per_step * 1e3, 2),
        "us_per_agent_step": round(per_step / max(n, 1) * 1e6, 2),
    }
    print("RESULT " + json.dumps(row))
    return row
'''

WORKLOADS = {
    "grid_epidemic": {
        "title": "Grid epidemic (SIR) with columns",
        "intro": (
            "An SIR epidemic on a Moore grid. `state` and `days_infected` are `Column`s, so the "
            "three model reporters are numpy comparisons and the data collector slices the "
            "column table. The per-agent work is the move and the infection loop over cellmates."
        ),
        "model": """
from modelly import Column, Model
from modelly.data.collector import DataCollector
from modelly.space import CellAgent, OrthogonalMooreGrid
from modelly.scenarios import Scenario

S, I, R = 0, 1, 2


class EpidemicScenario(Scenario):
    n: int = 2000
    side: int = 60
    infection_chance: float = 0.3
    recovery_time: int = 10
    initially_infected: int = 10


class Person(CellAgent):
    state = Column(int, default=S)
    days_infected = Column(int, default=0)

    def __init__(self, model, cell, infected=False):
        super().__init__(model)
        self.cell = cell
        if infected:
            self.state = I

    def step(self):
        self.cell = self.cell.neighborhood.select_random_cell()
        if self.state != I:
            return
        chance = self.scenario.infection_chance
        for other in self.cell.agents:
            if other.state == S and self.random.random() < chance:
                other.state = I
        self.days_infected += 1
        if self.days_infected >= self.scenario.recovery_time:
            self.state = R


class Epidemic(Model):
    def __init__(self, scenario=EpidemicScenario):
        super().__init__(scenario=scenario)
        self.grid = OrthogonalMooreGrid((scenario.side, scenario.side), torus=True, random=self.random)
        cells = self.random.choices(self.grid.all_cells.cells, k=scenario.n)
        infected = [i < scenario.initially_infected for i in range(scenario.n)]
        Person.create_agents(self, scenario.n, cells, infected=infected)
        self.datacollector = DataCollector(
            model_reporters={"S": lambda m: m.count(S), "I": lambda m: m.count(I), "R": lambda m: m.count(R)},
            agent_reporters={"state": "state"},
        )

    def count(self, state):
        return int((self.columns[Person].state == state).sum())

    def step(self):
        self.agents.shuffle_do("step")
        self.datacollector.collect(self)
""",
        "sizes": [
            (
                "2k agents, 60x60",
                "lambda: Epidemic(EpidemicScenario(n=2000, side=60, rng=1))",
                20,
            ),
            (
                "8k agents, 120x120",
                "lambda: Epidemic(EpidemicScenario(n=8000, side=120, rng=1))",
                20,
            ),
            (
                "32k agents, 240x240",
                "lambda: Epidemic(EpidemicScenario(n=32000, side=240, rng=1))",
                10,
            ),
        ],
    },
    "predator_prey_lifecycle": {
        "title": "Predator-prey: births and deaths every step",
        "intro": (
            "The bundled Wolf-Sheep model, scaled. Every step moves every animal, kills the "
            "starving and spawns offspring, so this is the agent-lifecycle workload: the cost "
            "per agent-step includes a share of births and deaths."
        ),
        "model": """
from modelly.examples.advanced.wolf_sheep.model import WolfSheep, WolfSheepScenario


def wolf_sheep(side, sheep, wolves):
    return lambda: WolfSheep(
        WolfSheepScenario(height=side, width=side, initial_sheep=sheep, initial_wolves=wolves,
                          sheep_reproduce=0.4, wolf_reproduce=0.2, grass_regrowth_time=10, rng=1)
    )
""",
        "sizes": [
            ("50x50, 250 sheep, 125 wolves", "wolf_sheep(50, 250, 125)", 20),
            ("100x100, 1000 sheep, 500 wolves", "wolf_sheep(100, 1000, 500)", 20),
            ("200x200, 4000 sheep, 2000 wolves", "wolf_sheep(200, 4000, 2000)", 10),
        ],
    },
    "flocking_continuous": {
        "title": "Flocking in continuous space: one tree versus n scans",
        "intro": (
            "The bundled Boids model answers neighbour queries for the whole flock with one "
            "KD-tree per step (`neighbors_within`). The `ScanBoids` variant below asks per "
            "agent instead, the O(n^2) pattern, to show where the tree starts to matter."
        ),
        "model": '''
from modelly.examples.basic.boid_flockers.agents import Boid
from modelly.examples.basic.boid_flockers.model import BoidFlockers, BoidsScenario


class ScanBoid(Boid):
    """A boid that scans the whole flock for its neighbours (O(n) per agent)."""

    def step(self):
        neighbors, _ = self.get_neighbors_in_radius(radius=self.vision)
        self.model.neighbor_lists = {self: neighbors}
        super().step()


class ScanBoids(BoidFlockers):
    """Boids without the per-step tree: every agent scans every position."""

    def step(self):
        self.agents.shuffle_do("step")
        self.update_average_heading()


def tree(n, side):
    return lambda: BoidFlockers(BoidsScenario(population_size=n, width=side, height=side, vision=10.0, rng=1))


def scan(n, side):
    def make():
        model = ScanBoids(BoidsScenario(population_size=n, width=side, height=side, vision=10.0, rng=1))
        for boid in model.agents:
            boid.__class__ = ScanBoid
        return model
    return make
''',
        "sizes": [
            ("500 boids, one tree per step", "tree(500, 100)", 10),
            ("500 boids, one scan per agent", "scan(500, 100)", 10),
            ("2000 boids, one tree per step", "tree(2000, 200)", 5),
            ("2000 boids, one scan per agent", "scan(2000, 200)", 5),
            ("5000 boids, one tree per step", "tree(5000, 300)", 3),
        ],
    },
    "network_diffusion": {
        "title": "Virus on a network",
        "intro": (
            "The bundled virus-on-network model on Erdos-Renyi graphs of growing size. Agents "
            "are fixed to nodes; the work per step is the neighbourhood walk of every infected node."
        ),
        "model": """
from modelly.examples import VirusOnNetwork


def virus(nodes):
    return lambda: VirusOnNetwork(num_nodes=nodes, avg_node_degree=6,
                                  initial_outbreak_size=max(1, nodes // 100), rng=1)
""",
        "sizes": [
            ("2k nodes", "virus(2000)", 10),
            ("8k nodes", "virus(8000)", 10),
            ("20k nodes", "virus(20000)", 5),
        ],
    },
}


def build(name: str, spec: dict) -> nbformat.NotebookNode:
    """Assemble one notebook from its workload spec."""
    nb = nbformat.v4.new_notebook()
    nb.metadata["kernelspec"] = {
        "name": "python3",
        "display_name": "Python 3",
        "language": "python",
    }
    nb.metadata["language_info"] = {"name": "python", "pygments_lexer": "ipython3"}
    runs = "\n".join(
        f'rows.append(bench("{label}", {factory}, steps={steps}))'
        for label, factory, steps in spec["sizes"]
    )
    cells = [
        nbformat.v4.new_markdown_cell(f"# {spec['title']}\n\n{spec['intro']}"),
        nbformat.v4.new_code_cell(HELPER.strip()),
        nbformat.v4.new_code_cell(spec["model"].strip()),
        nbformat.v4.new_code_cell(f"rows = []\n{runs}"),
        nbformat.v4.new_code_cell("pd.DataFrame(rows).set_index('label')"),
    ]
    nb.cells = cells
    return nb


def main() -> None:
    """Write every notebook."""
    for name, spec in WORKLOADS.items():
        path = HERE / f"{name}.ipynb"
        nbformat.write(build(name, spec), path)
        print(f"wrote {path.relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    main()
