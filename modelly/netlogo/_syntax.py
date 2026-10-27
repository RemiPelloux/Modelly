"""The NetLogo subset: tokens, the syntax tree, and the primitives the translator knows.

NetLogo has no statement separators: a primitive's arity says where its arguments end,
so every supported primitive is listed here with the number of inputs it takes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Expr",
    "Procedure",
    "Program",
    "Stmt",
    "Token",
    "UntranslatableError",
    "tokenize",
]

# Commands translated one to one: name -> number of inputs.
COMMANDS = {
    "clear-all": 0,
    "ca": 0,
    "reset-ticks": 0,
    "tick": 0,
    "die": 0,
    "stop": 0,
    "fd": 1,
    "forward": 1,
    "bk": 1,
    "back": 1,
    "rt": 1,
    "right": 1,
    "lt": 1,
    "left": 1,
    "setxy": 2,
    "move-to": 1,
}
# Commands that only change what the view shows: dropped, and listed in the report.
DISPLAY = {
    "set-default-shape": 2,
    "hide-turtle": 0,
    "ht": 0,
    "show-turtle": 0,
    "st": 0,
    "pen-down": 0,
    "pd": 0,
    "pen-up": 0,
    "pu": 0,
    "display": 0,
    "no-display": 0,
    "print": 1,
    "show": 1,
    "type": 1,
    "write": 1,
    "output-print": 1,
    "clear-output": 0,
    "update-plots": 0,
}
# Commands that take a block after their inputs: name -> (inputs, blocks).
BLOCK_COMMANDS = {"if": (1, 1), "ifelse": (1, 2), "repeat": (1, 1), "ask": (1, 1)}
# The two spellings of create-turtles.
CREATE_TURTLES = frozenset({"create-turtles", "crt"})
# Reporters: name -> number of inputs.
REPORTERS = {
    "random": 1,
    "random-float": 1,
    "one-of": 1,
    "count": 1,
    "any?": 1,
    "not": 1,
    "abs": 1,
    "sqrt": 1,
    "patch-here": 0,
    "neighbors": 0,
    "neighbors4": 0,
    "turtles-here": 0,
    "random-xcor": 0,
    "random-ycor": 0,
    "random-pxcor": 0,
    "random-pycor": 0,
    "ticks": 0,
    "turtles": 0,
    "patches": 0,
    "nobody": 0,
    "true": 0,
    "false": 0,
    "self": 0,
    "myself": 0,
    "world-width": 0,
    "world-height": 0,
    "min-pxcor": 0,
    "max-pxcor": 0,
    "min-pycor": 0,
    "max-pycor": 0,
}
# Infix operators and their precedence: a higher number binds tighter.
INFIX = {
    "or": 1,
    "xor": 1,
    "and": 2,
    "=": 3,
    "!=": 3,
    "<": 3,
    ">": 3,
    "<=": 3,
    ">=": 3,
    "+": 4,
    "-": 4,
    "*": 5,
    "/": 5,
    "mod": 5,
    "^": 6,
    "with": 8,
}
# A prefix reporter's input ends at the first infix operator weaker than this one:
# `random 10 + 1` is `(random 10) + 1`, `count turtles with [...]` counts the filter.
ARGUMENT_BINDING = INFIX["with"]

WORD = re.compile(r'"(?:[^"\\]|\\.)*"|[\[\]()]|[^\s\[\]()";]+')


class UntranslatableError(ValueError):
    """A construct outside the subset: the statement it is in needs a human."""


@dataclass(frozen=True)
class Token:
    """One word of the source, lower-cased (NetLogo is case-insensitive), and its line."""

    word: str
    line: int


@dataclass(frozen=True)
class Expr:
    """A reporter: ``num``, ``str``, ``name``, ``call`` (a prefix reporter), ``op``.

    ``value`` is the number, string, name or operator; ``args`` the inputs.
    """

    kind: str
    value: Any = None
    args: tuple[Expr, ...] = ()


@dataclass(frozen=True)
class Stmt:
    """A command: its kind, the name it acts on, its inputs, its blocks, its line.

    Kinds: ``set``, ``let``, ``if``, ``ifelse``, ``repeat``, ``ask``, ``create``,
    ``hatch``, ``sprout``, ``report``, ``call`` (a user procedure), ``command`` (a
    primitive of ``COMMANDS``), ``display`` and ``untranslated`` (with the source in
    ``text``).
    """

    kind: str
    name: str = ""
    args: tuple[Expr, ...] = ()
    blocks: tuple[tuple[Stmt, ...], ...] = ()
    line: int = 0
    text: str = ""


@dataclass
class Procedure:
    """``to name [params] ... end`` or ``to-report``: its inputs and its body."""

    name: str
    params: list[str]
    reporter: bool
    line: int
    body: tuple[Stmt, ...] = ()
    tokens: list[Token] = field(default_factory=list)


@dataclass
class Program:
    """The declarations and procedures of a NetLogo code tab."""

    globals: list[str] = field(default_factory=list)
    breeds: dict[str, str] = field(default_factory=dict)  # plural -> singular
    turtle_vars: list[str] = field(default_factory=list)
    patch_vars: list[str] = field(default_factory=list)
    breed_vars: dict[str, list[str]] = field(default_factory=dict)
    procedures: dict[str, Procedure] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)  # the source, for the report

    def turtle_variables(self) -> set[str]:
        """Every variable a turtle of any breed owns."""
        own = set(self.turtle_vars)
        for names in self.breed_vars.values():
            own.update(names)
        return own


def tokenize(code: str) -> list[Token]:
    """The words of ``code`` without comments; strings keep their quotes."""
    tokens = []
    for number, line in enumerate(code.splitlines(), start=1):
        for match in WORD.finditer(strip_comment(line)):
            word = match.group()
            tokens.append(Token(word if word.startswith('"') else word.lower(), number))
    return tokens


def strip_comment(line: str) -> str:
    """``line`` without its ``;`` comment, leaving semicolons inside strings."""
    quoted = False
    for index, char in enumerate(line):
        if char == '"' and (index == 0 or line[index - 1] != "\\"):
            quoted = not quoted
        elif char == ";" and not quoted:
            return line[:index]
    return line
