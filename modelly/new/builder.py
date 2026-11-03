"""The model builder: a few choices in a form, one ordinary Modelly ``model.py`` out.

For teaching. A ``ModelSpec`` names one kind of agent, how many there are, the size of the
grid they live on, and their behaviours, picked from ``BEHAVIOURS`` (walk to a random
neighbouring cell, give wealth to a cellmate, catch an infection from cellmates, recover).
``build_code(spec)`` writes a single module with a ``Scenario`` holding every parameter, the
agent class with its ``Column`` attributes and one method per behaviour, and the model with
its grid and a ``DataCollector``: code a student reads, runs and changes, which passes
``modelly lint``. Studio's Builder tab is a form over it.
"""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass, field

IDENTIFIER = re.compile(r"^[A-Z][A-Za-z0-9]*$")


@dataclass(frozen=True)
class Behaviour:
    """One behaviour: its columns, its parameters, its method body and its reporters."""

    summary: str
    columns: tuple[tuple[str, str, str], ...]  # (name, type, default)
    parameters: tuple[tuple[str, str, str], ...]  # (name, type, default)
    body: tuple[str, ...]
    reporters: tuple[tuple[str, str], ...] = ()  # (name, expression of model)


BEHAVIOURS: dict[str, Behaviour] = {
    "walk": Behaviour("walks to a random neighbouring cell", (), (),
                      ("self.cell = self.cell.neighborhood.select_random_cell()",),
                      (("occupied_cells", "len({{agent.cell for agent in model.agents}})"),)),
    "give": Behaviour(
        "gives one unit of wealth to a random cellmate", (("wealth", "int", "1"),), (),
        ("cellmates = [a for a in self.cell.agents if a is not self]",
         "if self.wealth > 0 and cellmates:",
         "    self.random.choice(cellmates).wealth += 1",
         "    self.wealth -= 1"),
        (("mean_wealth", "float(np.mean(model.columns[{agent}].wealth))"),),
    ),
    "infect": Behaviour(
        "catches the infection from a cellmate, with probability `infection`",
        (("infected", "bool", "False"),), (("infection", "float", "0.3"),),
        ("sick = any(a.infected for a in self.cell.agents if a is not self)",
         "if self.infected or not sick:",
         "    return",
         "if self.random.random() < self.model.scenario.infection:",
         "    self.infected = True"),
        (("infected", "int(np.count_nonzero(model.columns[{agent}].infected))"),),
    ),
    "recover": Behaviour(
        "recovers with probability `recovery` each step", (("infected", "bool", "False"),),
        (("recovery", "float", "0.1"),),
        ("if self.infected and self.random.random() < self.model.scenario.recovery:",
         "    self.infected = False"),
    ),
}  # fmt: skip


class BuilderError(ValueError):
    """A spec the builder cannot write a model from; the message says why."""


@dataclass(frozen=True)
class ModelSpec:
    """What the form chose.

    Attributes:
        name: the model class's name (CapWords); the agent is ``agent``.
        agent: the agent class's name (CapWords).
        count: how many agents.
        width, height: the grid.
        behaviours: names of ``BEHAVIOURS``, in the order the agent does them each step.
        initially_infected: agents infected at the start (with ``infect``).
    """

    name: str = "Classroom"
    agent: str = "Student"
    count: int = 100
    width: int = 20
    height: int = 20
    behaviours: tuple[str, ...] = ("walk",)
    initially_infected: int = 5
    seed: int = 42
    steps: int = 100
    extra: dict[str, str] = field(default_factory=dict)

    def check(self) -> None:
        """Refuse names that are not class names, unknown behaviours, bad sizes."""
        for label, value in (("model", self.name), ("agent", self.agent)):
            if (
                not IDENTIFIER.match(value)
                or keyword.iskeyword(value)
                or value in ("Model", "Agent")
            ):
                raise BuilderError(
                    f"the {label} name {value!r} must be a CapWords class name"
                )
        unknown = [b for b in self.behaviours if b not in BEHAVIOURS]
        if unknown or not self.behaviours:
            raise BuilderError(
                f"behaviours are some of {sorted(BEHAVIOURS)}, not {unknown}"
            )
        if min(self.count, self.width, self.height) < 1:
            raise BuilderError("count, width and height must be at least 1")


def _merged(spec: ModelSpec, part: str) -> list[tuple[str, ...]]:
    """The columns, parameters or reporters of every chosen behaviour, each once."""
    seen: dict[str, tuple[str, ...]] = {}
    for name in spec.behaviours:
        for item in getattr(BEHAVIOURS[name], part):
            seen.setdefault(item[0], item)
    return list(seen.values())


def _scenario(spec: ModelSpec) -> list[str]:
    """The Scenario class: sizes, behaviours' parameters and the run length."""
    lines = [f"class {spec.name}Scenario(Scenario):", '    """Every parameter of the model, with its default."""', "",
             f"    count: int = {spec.count}", f"    width: int = {spec.width}",
             f"    height: int = {spec.height}", f"    steps: int = {spec.steps}"]  # fmt: skip
    lines += [f"    {n}: {t} = {d}" for n, t, d in _merged(spec, "parameters")]
    if "infect" in spec.behaviours:
        lines.append(f"    initially_infected: int = {spec.initially_infected}")
    return lines


def _agent(spec: ModelSpec) -> list[str]:
    """The agent class: its columns, its behaviours and its step."""
    lines = [f"class {spec.agent}(CellAgent):", '    """Each step, it:', ""]
    lines += [f"    - {BEHAVIOURS[b].summary}" for b in spec.behaviours]
    lines += ['    """', ""]
    columns = [
        f"    {n} = Column({t}, default={d})" for n, t, d in _merged(spec, "columns")
    ]
    lines += [*columns, ""] if columns else []
    lines += ["    def __init__(self, model, cell):", '        """An agent on ``cell``."""',
              "        super().__init__(model)", "        self.cell = cell", "",
              "    def step(self):", '        """Its behaviours, in order."""']  # fmt: skip
    lines += [f"        self.{b}()" for b in spec.behaviours]
    for name in spec.behaviours:
        behaviour = BEHAVIOURS[name]
        lines += [
            "",
            f"    def {name}(self):",
            f'        """It {behaviour.summary}."""',
        ]
        lines += [f"        {line}" for line in behaviour.body]
    return lines


def _model(spec: ModelSpec) -> list[str]:
    """The model class: the grid, the agents, the reporters, the step."""
    reporters = [f'            "{n}": {n},' for n, _ in _merged(spec, "reporters")]
    lines = [f"class {spec.name}(Model):", f'    """{spec.agent}s on a wrapping grid."""', "",
             f"    def __init__(self, scenario: {spec.name}Scenario = {spec.name}Scenario):",
             '        """The grid and the agents, placed at random."""',
             "        super().__init__(scenario=scenario)", "        s = self.scenario",
             "        self.grid = OrthogonalMooreGrid(",
             "            (s.width, s.height), torus=True, random=self.random",
             "        )",
             "        cells = self.random.choices(self.grid.all_cells.cells, k=s.count)",
             f"        {spec.agent}.create_agents(self, s.count, cells)"]  # fmt: skip
    if "infect" in spec.behaviours:
        lines += ["        for agent in list(self.agents)[: s.initially_infected]:", "            agent.infected = True"]  # fmt: skip
    lines += ["        self.datacollector = DataCollector(", "            model_reporters={",
              *[r.replace("            ", "                ", 1) for r in reporters], "            }",
              "        )", "        self.datacollector.collect(self)", "", "    def step(self):",
              '        """Every agent acts once, in a random order; then the data is recorded."""',
              '        self.agents.shuffle_do("step")', "        self.datacollector.collect(self)"]  # fmt: skip
    return lines


def _reporters(spec: ModelSpec) -> list[str]:
    """One module-level function per reporter, as the DataCollector reads them."""
    lines: list[str] = []
    for name, expression in _merged(spec, "reporters"):
        lines += [f"def {name}(model):", f'    """The model\'s {name.replace("_", " ")}."""',
                  f"    return {expression.format(agent=spec.agent)}", "", ""]  # fmt: skip
    return lines


def _imports(spec: ModelSpec) -> list[str]:
    """The module docstring and the imports the chosen behaviours need."""
    numpy = any("np." in e for _, e in _merged(spec, "reporters"))
    names = (
        ["Column", "DataCollector", "Model"]
        if _merged(spec, "columns")
        else ["DataCollector", "Model"]
    )
    return [f'"""{spec.name}: written by the Modelly model builder; change anything."""', "",
            *(["import numpy as np", ""] if numpy else []),
            f"from modelly import {', '.join(names)}",
            "from modelly.scenarios import Scenario",
            "from modelly.space import CellAgent, OrthogonalMooreGrid", "", ""]  # fmt: skip


def build_code(spec: ModelSpec) -> str:
    """The ``model.py`` the spec describes.

    Raises:
        BuilderError: for a spec ``ModelSpec.check`` refuses.
    """
    spec.check()
    head = _imports(spec)
    body = [
        *_scenario(spec),
        "",
        "",
        *_agent(spec),
        "",
        "",
        *_reporters(spec),
        *_model(spec),
    ]
    run = ["", "", 'if __name__ == "__main__":',
           f"    model = {spec.name}({spec.name}Scenario(rng={spec.seed}))",
           f"    model.run_for({spec.name}Scenario.steps)",
           "    print(model.datacollector.get_model_vars_dataframe().tail())"]  # fmt: skip
    return "\n".join(head + body + run) + "\n"
