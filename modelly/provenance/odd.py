"""An ODD protocol skeleton (Grimm et al.'s Overview, Design concepts, Details) for a model.

The seven ODD elements are written from what :mod:`modelly.provenance.odd_facts` finds
in the code; every place only the modeller can fill holds a ``TODO`` marker.
"""

from __future__ import annotations

from typing import Any

from modelly.core.model import Model
from modelly.provenance.odd_facts import AgentFacts, ModelFacts, model_facts

TODO = "TODO"
SECTIONS = (
    "Purpose and patterns",
    "Entities, state variables and scales",
    "Process overview and scheduling",
    "Design concepts",
    "Initialization",
    "Input data",
    "Submodels",
)
DESIGN_CONCEPTS = (
    "Basic principles",
    "Emergence",
    "Adaptation",
    "Objectives",
    "Learning",
    "Prediction",
    "Sensing",
    "Interaction",
    "Stochasticity",
    "Collectives",
    "Observation",
)


def _table(header: tuple[str, ...], rows: list[tuple[Any, ...]]) -> list[str]:
    """A Markdown table; ``[]`` when there are no rows."""
    if not rows:
        return []
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += [
        "| " + " | ".join(f"`{c}`" if c != "" else "" for c in row) + " |"
        for row in rows
    ]
    return [*lines, ""]


def purpose(facts: ModelFacts) -> list[str]:
    """Element 1: purpose and patterns."""
    doc = facts.doc or f"{TODO}: what the model is for."
    return [doc, "", f"{TODO}: the patterns the model is meant to reproduce.", ""]


def _agent_entity(agent: AgentFacts) -> list[str]:
    """One agent class: summary, columns and attributes."""
    lines = [
        f"### {agent.name}",
        "",
        agent.summary or f"{TODO}: what this agent represents.",
        "",
    ]
    lines.append(f"{agent.count} at initialization.")
    lines.append("")
    lines += _table(("Column", "dtype", "Default"), agent.columns)
    lines += _table(("Attribute", "Type at initialization"), agent.attributes)
    return [*lines, f"{TODO}: meaning and units of each state variable.", ""]


def entities(facts: ModelFacts) -> list[str]:
    """Element 2: agents, global variables, space and time."""
    lines = []
    for agent in facts.agents:
        lines += _agent_entity(agent)
    lines += ["### Global state variables", ""]
    lines += _table(("Attribute", "Type"), facts.globals) or ["None found.", ""]
    lines += ["### Spatial scale", ""]
    spaces = [
        (n, c, ", ".join(f"{k}={v}" for k, v in t.items())) for n, c, t in facts.spaces
    ]
    lines += _table(("Attribute", "Space", "Traits"), spaces) or ["No space found.", ""]
    lines += [f"{TODO}: what one cell or unit of distance represents.", ""]
    lines += ["### Temporal scale", "", f"One step represents {TODO} (time unit).", ""]
    return lines


def process(facts: ModelFacts) -> list[str]:
    """Element 3: the statements of ``step`` in order."""
    if not facts.step:
        return [
            f"{TODO}: the model's step could not be read; describe the schedule.",
            "",
        ]
    lines = ["Each step (`Model.step`, once per time unit) runs:", ""]
    lines += [f"{i}. `{statement}`" for i, statement in enumerate(facts.step, start=1)]
    if facts.dispatched:
        called = ", ".join(f"`{name}`" for name in facts.dispatched)
        lines += ["", f"Agent methods called: {called} (see Submodels)."]
    return [*lines, "", f"{TODO}: the order of updates and why.", ""]


def _observation(facts: ModelFacts) -> str:
    """What the DataCollector records, for the Observation concept."""
    named = [
        f"{level}: {', '.join(names)}"
        for level, names in facts.reporters.items()
        if names
    ]
    return (
        "DataCollector reporters (" + "; ".join(named) + ")." if named else f"{TODO}."
    )


def design(facts: ModelFacts) -> list[str]:
    """Element 4: the eleven design concepts."""
    hints = {
        "Observation": _observation(facts),
        "Stochasticity": "Draws come from `model.random` and `model.rng`, seeded by the "
        f"scenario's `rng`. {TODO}: which processes are random.",
    }
    return [f"- **{c}**: {hints.get(c, f'{TODO}.')}" for c in DESIGN_CONCEPTS] + [""]


def initialization(facts: ModelFacts) -> list[str]:
    """Element 5: scenario parameters and the initial population."""
    name, defaults, values = facts.scenario
    rows = [
        (k, repr(defaults[k]) if k in defaults else "", repr(v))
        for k, v in values.items()
    ]
    lines = [f"Parameters come from `{name}`:", ""]
    lines += _table(("Parameter", "Default", "Value used"), rows) or [
        "No parameters.",
        "",
    ]
    counts = ", ".join(f"{a.count} {a.name}" for a in facts.agents) or "no agents"
    lines += [f"At initialization the model holds {counts}.", ""]
    return [*lines, f"{TODO}: how initial states and positions are chosen.", ""]


def input_data(facts: ModelFacts) -> list[str]:
    """Element 6: external data (none can be detected from the code)."""
    return [f"{TODO}: external data read during the run, or 'None'.", ""]


def submodels(facts: ModelFacts) -> list[str]:
    """Element 7: each agent method, scheduled ones first."""
    lines = []
    for agent in facts.agents:
        order = {name: i for i, name in enumerate(facts.dispatched)}
        methods = sorted(agent.methods, key=lambda m: order.get(m[0], len(order)))
        for method, doc in methods:
            lines += [f"### {agent.name}.{method}", "", doc or f"{TODO}.", ""]
            lines += [f"{TODO}: equations, parameters and their values.", ""]
    return lines or [f"{TODO}: describe each process of the schedule.", ""]


WRITERS = (purpose, entities, process, design, initialization, input_data, submodels)


def odd_markdown(model: Model[Any, Any]) -> str:
    """The ODD skeleton of a built model, as Markdown."""
    facts = model_facts(model)
    lines = [
        f"# ODD protocol: {facts.name}",
        "",
        f"Skeleton generated by `modelly odd` from the code. Replace every {TODO}.",
        "",
    ]
    for number, (title, writer) in enumerate(zip(SECTIONS, WRITERS), start=1):
        lines += [f"## {number}. {title}", "", *writer(facts)]
    return "\n".join(lines).rstrip("\n") + "\n"
