"""From NetLogo names to Python ones, and which object a variable lives on.

NetLogo names may hold ``-`` and ``?`` and are case-insensitive: ``grass-regrowth-time``
becomes ``grass_regrowth_time`` and ``grass?`` becomes ``grass``. A name that would
hide an attribute of the runtime (a slider called ``width``) gets a trailing ``_``.
Inside a turtle's code, its own variables are ``turtle.energy`` and the variables of
the patch under it are ``turtle.patch.pcolor``, as in NetLogo.
"""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass, field

from modelly.netlogo._expressions import PATCH_BUILTINS, TURTLE_BUILTINS
from modelly.netlogo._syntax import Program, UntranslatableError
from modelly.netlogo.agents import Patch, Turtle
from modelly.netlogo.colors import NAMES as COLOR_NAMES
from modelly.netlogo.runtime import NetLogoModel, NetLogoScenario

__all__ = ["Context", "Names", "Scope", "class_name", "python_name"]

NOT_IDENTIFIER = re.compile(r"[^a-z0-9_]")
READ_ONLY = frozenset({"xcor", "ycor", "who", "pxcor", "pycor"})
ARTICLES = ("a-", "an-")
# Attributes of the runtime classes and instances: a NetLogo name equal to one is renamed.
MODEL_RESERVED = frozenset(
    {*dir(NetLogoModel), *dir(NetLogoScenario), "world", "patches", "patch_index"}
    | {"width", "height", "ticks", "datacollector", "random", "rng", "running"}
    | {"min_pxcor", "max_pxcor", "min_pycor", "max_pycor", "columns", "time"}
)
AGENT_INSTANCE = frozenset({"model", "unique_id", "alive"})
TURTLE_RESERVED = frozenset(dir(Turtle)) | AGENT_INSTANCE
PATCH_RESERVED = (
    frozenset(dir(Patch)) | AGENT_INSTANCE | {"site", "neighbors4", "neighbors8"}
)
OBSERVER = "observer"


def python_name(word: str, reserved: frozenset[str] = frozenset()) -> str:
    """A Python identifier for a NetLogo name: ``-`` to ``_``, no ``?``, no keyword."""
    name = NOT_IDENTIFIER.sub("_", word.lower().replace("?", ""))
    if not name or name[0].isdigit():
        name = "_" + name
    if keyword.iskeyword(name) or name in reserved:
        name += "_"
    return name


def class_name(word: str) -> str:
    """A class name for a NetLogo name: ``a-sheep`` -> ``Sheep``, ``fire`` -> ``Fire``."""
    for article in ARTICLES:
        word = word.removeprefix(article)
    parts = python_name(word).split("_")
    return "".join(part.capitalize() for part in parts if part) or "Breed"


@dataclass
class Scope:
    """One generated Python function: its locals, their agent kinds, its nonlocals."""

    locals: set[str] = field(default_factory=set)
    kinds: dict[str, str] = field(default_factory=dict)
    nonlocals: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Context:
    """Who runs the code: the observer, or a turtle or patch held in ``var``.

    ``outer`` is the context that asked (NetLogo's ``myself``).
    """

    kind: str = OBSERVER
    var: str = ""
    outer: Context | None = None


class Names:
    """The Python name and owner of every variable of one program."""

    def __init__(self, program: Program, sliders: list[str]) -> None:
        """Index the globals, sliders, turtle and patch variables of ``program``."""
        self.model_names = {*program.globals, *sliders}
        self.turtle_names = program.turtle_variables() | TURTLE_BUILTINS
        self.patch_names = set(program.patch_vars) | PATCH_BUILTINS
        self.colors: set[str] = set()  # the color constants used, for the imports

    def model(self, word: str) -> str:
        """The attribute of a global, slider or procedure on the model."""
        return python_name(word, MODEL_RESERVED)

    def turtle(self, word: str) -> str:
        """The attribute of a turtle variable."""
        if word in TURTLE_BUILTINS:
            return python_name(word)
        return python_name(word, TURTLE_RESERVED)

    def patch(self, word: str) -> str:
        """The attribute of a patch variable."""
        if word in PATCH_BUILTINS:
            return python_name(word)
        return python_name(word, PATCH_RESERVED)

    def agent_variable(self, word: str, context: Context) -> str | None:
        """``turtle.x`` or ``turtle.patch.x`` or ``patch.x``; None when not an agent's."""
        if context.kind == "turtle" and word in self.turtle_names:
            return f"{context.var}.{self.turtle(word)}"
        if context.kind == "turtle" and word in self.patch_names:
            return f"{context.var}.patch.{self.patch(word)}"
        if context.kind == "patch" and word in self.patch_names:
            return f"{context.var}.{self.patch(word)}"
        if (
            word in self.turtle_names | self.patch_names
            and word not in self.model_names
        ):
            raise UntranslatableError(
                f"{word!r} is a turtle or patch variable, read here by the {context.kind}"
            )
        return None

    def read(self, word: str, context: Context, scopes: list[Scope]) -> str:
        """The Python expression that reads variable ``word``.

        Raises:
            UntranslatableError: for an agent variable outside the agent's code.
        """
        local = python_name(word)
        if any(local in scope.locals for scope in scopes):
            return local
        if word in COLOR_NAMES and word not in self.model_names:
            self.colors.add(COLOR_NAMES[word])
            return COLOR_NAMES[word]
        found = self.agent_variable(word, context)
        if found is not None:
            return found
        if word in self.model_names:
            return f"self.{self.model(word)}"
        raise UntranslatableError(f"unknown variable {word!r}")

    def write(self, word: str, context: Context, scopes: list[Scope]) -> str:
        """The Python target that ``set word ...`` assigns; marks outer locals nonlocal.

        Raises:
            UntranslatableError: for a read-only variable or an unknown one.
        """
        if word in READ_ONLY:
            raise UntranslatableError(f"set of the read-only variable {word!r}")
        local = python_name(word)
        for depth, scope in enumerate(reversed(scopes)):
            if local in scope.locals:
                if depth:
                    scopes[-1].nonlocals.add(local)
                return local
        if word in COLOR_NAMES and word not in self.model_names:
            raise UntranslatableError(f"set of the color {word!r}")
        return self.read(word, context, scopes)
