"""The text of a translated module: imports, Scenario, agent classes and the model."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from modelly.netlogo._emit_stmt import INDENT

if TYPE_CHECKING:
    from modelly.netlogo._translate import Translator

__all__ = ["write_module"]

HEADER = '''"""{title}: translated from NetLogo by modelly.netlogo.

{review}
"""
'''
REVIEW_NONE = "Every line of the NetLogo code tab was translated."
REVIEW_SOME = (
    "{count} line(s) were not translated: search for NETLOGO and finish them by hand."
)


def strings(names: list[str]) -> str:
    """A Python tuple of string literals, double-quoted as ruff wants."""
    items = ", ".join(json.dumps(name) for name in names)
    return f"({items},)" if len(names) == 1 else f"({items})"


def imports(translator: Translator) -> list[str]:
    """The import lines the module needs, sorted as isort sorts them."""
    lines = ["import math", ""] if translator.uses_math else []
    agents = []
    if translator.program.patch_vars:
        agents.append("Patch")
    if translator.turtle_class != "None":
        agents.append("Turtle")
    if agents:
        lines.append(f"from modelly.netlogo.agents import {', '.join(agents)}")
    colors = sorted(translator.names.colors)
    if colors:
        lines.append(f"from modelly.netlogo.colors import {', '.join(colors)}")
    lines.append("from modelly.netlogo.runtime import NetLogoModel, NetLogoScenario")
    return lines


def scenario(translator: Translator) -> list[str]:
    """The Scenario: one field per slider and switch, then the world."""
    world = translator.interface.world
    lines = [
        f"class {translator.title}Scenario(NetLogoScenario):",
        f'{INDENT}"""The sliders and switches of the interface, and the world."""',
        "",
    ]
    for found in translator.interface.fields:
        lines.append(
            f"{INDENT}{translator.names.model(found.name)}: {found.kind} = {found.default!r}"
        )
    for name in ("min_pxcor", "max_pxcor", "min_pycor", "max_pycor"):
        lines.append(f"{INDENT}{name}: int = {getattr(world, name)}")
    return [*lines, f"{INDENT}wrap: bool = {world.wrap}"]


def agent_class(name: str, base: str, doc: str, own: list[str]) -> list[str]:
    """One agent class with its docstring and ``own`` variables."""
    lines = ["", "", f"class {name}({base}):", f'{INDENT}"""{doc}"""']
    return [*lines, "", f"{INDENT}own = {strings(own)}"] if own else lines


PATCH_DOC = "A patch, with the variables of ``patches-own``."
TURTLE_DOC = "A turtle, with the variables of ``turtles-own``."
BREED_DOC = "A turtle of the ``{plural}`` breed (one of them: ``{single}``)."


def agent_classes(translator: Translator) -> list[str]:
    """The patch class, the turtle class and one class per breed."""
    program, names, title = translator.program, translator.names, translator.title
    lines: list[str] = []
    if program.patch_vars:
        own = [names.patch(v) for v in program.patch_vars]
        lines += agent_class(f"{title}Patch", "Patch", PATCH_DOC, own)
    if translator.turtle_class == "None":
        return lines
    own = [names.turtle(v) for v in program.turtle_vars]
    lines += agent_class(translator.turtle_class, "Turtle", TURTLE_DOC, own)
    for plural, single in program.breeds.items():
        own = [names.turtle(v) for v in program.breed_vars.get(plural, [])]
        doc = BREED_DOC.format(plural=plural, single=single)
        lines += agent_class(
            translator.breeds[plural], translator.turtle_class, doc, own
        )
    return lines


def model_attributes(translator: Translator) -> list[str]:
    """The class attributes that tell the runtime the program's classes and names."""
    program, names, title = translator.program, translator.names, translator.title
    lines = []
    if program.patch_vars:
        lines.append(f"patch_class = {title}Patch")
    if translator.turtle_class != "None":
        lines.append(f"turtle_class = {translator.turtle_class}")
    pairs = [
        f"({json.dumps(names.model(p))}, {cls})" for p, cls in translator.breeds.items()
    ]
    if pairs:
        lines.append(f"breeds = ({', '.join(pairs)}{',' if len(pairs) == 1 else ''})")
    sliders = [names.model(f.name) for f in translator.interface.fields]
    if sliders:
        lines.append(f"sliders = {strings(sliders)}")
    if program.globals:
        lines.append(
            f"global_names = {strings([names.model(g) for g in program.globals])}"
        )
    return [INDENT + line for line in lines]


def model_class(translator: Translator, methods: list[str]) -> list[str]:
    """The model: its attributes, ``__init__`` running ``setup``, ``step`` running ``go``."""
    title, procedures = translator.title, translator.program.procedures
    setup = [f"{INDENT * 2}self.setup()"] if "setup" in procedures else []
    go = [f"{INDENT * 2}self.go()"] if "go" in procedures else []
    return [
        "",
        "",
        f"class {title}Model(NetLogoModel):",
        f'{INDENT}"""{title}: ``setup`` runs when the model is created, each step runs ``go``."""',
        "",
        *model_attributes(translator),
        "",
        f"{INDENT}def __init__(self, scenario: {title}Scenario = {title}Scenario):",
        f'{INDENT * 2}"""Build the world from ``scenario``, then run ``setup``."""',
        f"{INDENT * 2}super().__init__(scenario=scenario)",
        *setup,
        "",
        f"{INDENT}def step(self):",
        f'{INDENT * 2}"""One tick: run ``go``."""',
        *go,
        *methods,
    ]


def write_module(translator: Translator, methods: list[str]) -> str:
    """The whole module, ending with one newline."""
    count = len({issue.line for issue in translator.issues if not issue.display_only})
    review = REVIEW_SOME.format(count=count) if count else REVIEW_NONE
    parts = [
        HEADER.format(title=translator.title, review=review),
        *imports(translator),
        "",
        "",
        *scenario(translator),
        *agent_classes(translator),
        *model_class(translator, methods),
    ]
    return "\n".join(parts).rstrip() + "\n"
