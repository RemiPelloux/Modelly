"""What an ODD description can say about a model by looking at it.

The model is built (not run) and inspected: its agent classes and their columns and
attributes, its spaces, its scenario, its DataCollector, and the statements and agent
methods of its ``step``. Source that cannot be read (a class made at runtime) gives
empty lists, never an error.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from dataclasses import dataclass, field
from typing import Any

from modelly.core.model import Model
from modelly.provenance.outputs import find_collector
from modelly.space import DiscreteSpace
from modelly.space.continuous.space import ContinuousSpace

# AgentSet methods whose first argument names the agent method they call.
DISPATCH = frozenset({"do", "shuffle_do", "map"})
SCALARS = (bool, int, float, str)
# Scalars every Model sets itself; they are not the modeller's global variables.
MODEL_BOOKKEEPING = frozenset({"running", "time", "agent_id_counter"})
SPACE_TRAITS = ("dimensions", "torus", "capacity", "width", "height")


@dataclass
class AgentFacts:
    """One agent class: population at build time, columns, attributes, methods."""

    name: str
    summary: str
    count: int
    columns: list[tuple[str, str, Any]] = field(default_factory=list)
    attributes: list[tuple[str, str]] = field(default_factory=list)
    methods: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class ModelFacts:
    """Everything :mod:`modelly.provenance.odd` writes down about a model."""

    name: str
    doc: str
    agents: list[AgentFacts]
    globals: list[tuple[str, str]]
    spaces: list[tuple[str, str, dict]]
    scenario: tuple[str, dict, dict]
    step: list[str]
    dispatched: list[str]
    reporters: dict[str, list[str]]


def summary(obj: Any) -> str:
    """The first paragraph of ``obj``'s own docstring, on one line, or ``""``."""
    doc = inspect.getdoc(obj) or ""
    return " ".join(doc.split("\n\n")[0].split())


def step_body(cls: type[Model]) -> list[ast.stmt]:
    """The statements of ``cls.step``, docstring excluded; [] when unreadable."""
    try:
        source = textwrap.dedent(inspect.getsource(cls.step))
    except (OSError, TypeError):
        return []
    function = ast.parse(source).body[0]
    body = list(getattr(function, "body", []))
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
    ):
        body = body[1:]
    return body


def dispatched_methods(body: list[ast.stmt]) -> list[str]:
    """Agent method names passed as strings to do / shuffle_do / map, in order."""
    names = []
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        first = node.args[0] if node.args else None
        value = first.value if isinstance(first, ast.Constant) else None
        if node.func.attr in DISPATCH and isinstance(value, str) and value not in names:
            names.append(value)
    return names


def _own_methods(cls: type) -> list[tuple[str, str]]:
    """Public functions defined on ``cls`` itself, with their summaries."""
    return [
        (name, summary(value))
        for name, value in vars(cls).items()
        if inspect.isfunction(value) and not name.startswith("_")
    ]


def agent_facts(cls: type, agents: Any) -> AgentFacts:
    """Facts about one agent class from its declaration and a live instance."""
    columns = [(n, str(c.dtype), c.default) for n, c in cls.column_specs().items()]
    sample = next(iter(agents), None)
    attributes = []
    if sample is not None:
        attributes = [
            (name, type(value).__name__)
            for name, value in getattr(sample, "__dict__", {}).items()
            if not name.startswith("_") and name != "model"
        ]
    return AgentFacts(
        cls.__name__, summary(cls), len(agents), columns, attributes, _own_methods(cls)
    )


def space_facts(model: Model) -> list[tuple[str, str, dict]]:
    """(attribute, class, traits) for each space the model holds."""
    found = []
    for name, value in vars(model).items():
        if isinstance(value, DiscreteSpace | ContinuousSpace):
            traits = {t: getattr(value, t) for t in SPACE_TRAITS if hasattr(value, t)}
            found.append((name, type(value).__name__, traits))
    return found


def global_facts(model: Model) -> list[tuple[str, str]]:
    """Public scalar attributes of the model: its global state variables."""
    return [
        (name, type(value).__name__)
        for name, value in vars(model).items()
        if not name.startswith("_")
        and name not in MODEL_BOOKKEEPING
        and isinstance(value, SCALARS)
    ]


def reporter_facts(model: Model) -> dict[str, list[str]]:
    """The DataCollector's reporter names by level."""
    collector = find_collector(model)
    if collector is None:
        return {}
    return {
        "model": list(collector.model_reporters),
        "agent": list(collector.agent_reporters),
        "tables": list(collector.tables),
    }


def model_facts(model: Model) -> ModelFacts:
    """Inspect a built model."""
    cls = type(model)
    body = step_body(cls)
    scenario = model.scenario
    agents = [agent_facts(t, s) for t, s in model.agents_by_type.items()]
    return ModelFacts(
        name=cls.__name__,
        doc=summary(cls),
        agents=agents,
        globals=global_facts(model),
        spaces=space_facts(model),
        scenario=(type(scenario).__name__, scenario._scenario_defaults, dict(scenario)),
        step=[ast.unparse(statement) for statement in body],
        dispatched=dispatched_methods(body),
        reporters=reporter_facts(model),
    )
