"""Shared fixtures for the provenance tests: example targets and a recorded run."""

import textwrap
from pathlib import Path

import pytest

import modelly.examples
from modelly.provenance import RunSpec, run_study

EXAMPLES = Path(modelly.examples.__file__).parent / "basic"
BOLTZMANN = f"{EXAMPLES / 'boltzmann_wealth_model' / 'model.py'}:BoltzmannWealth"
SCHELLING = "modelly.examples.basic.schelling.model:Schelling"
STEPS = 5

TINY_SOURCE = """
from modelly import Agent, Model
from modelly.data.collector import DataCollector


class Walker(Agent):
    def step(self):
        self.x = getattr(self, "x", 0.0) + self.random.random()


class Walk(Model):
    def __init__(self, n=4, rng=None):
        super().__init__(rng=rng)
        Walker.create_agents(self, n)
        self.datacollector = DataCollector(
            model_reporters={"agents": lambda m: len(m.agents)},
            agent_reporters={"x": "x"},
        )

    def step(self):
        self.agents.shuffle_do("step")
        self.datacollector.collect(self)


class Broken(Model):
    def step(self):
        raise RuntimeError("boom")
"""


@pytest.fixture
def tiny_model(tmp_path) -> Path:
    """A small model file outside the package, with a sibling module-free layout."""
    folder = tmp_path / "model"
    folder.mkdir()
    path = folder / "walk.py"
    path.write_text(textwrap.dedent(TINY_SOURCE), encoding="utf-8")
    return path


@pytest.fixture
def boltzmann_run(tmp_path) -> Path:
    """A recorded Boltzmann run; the run folder."""
    out = tmp_path / "runs"
    scenario = tmp_path / "scenario.toml"
    scenario.write_text("seed = 3\nn = 30\n", encoding="utf-8")
    run_study(RunSpec(BOLTZMANN, out=out, steps=STEPS, scenario=scenario))
    return out
