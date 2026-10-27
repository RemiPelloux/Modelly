"""Writing NetLogo reporters as Python expressions.

Each expression comes back with its Python precedence, so operands get parentheses
only where Python needs them. Agent sets are lists: ``patches with [pcolor = red]``
becomes ``[patch for patch in self.patches if patch.pcolor == RED]``.
"""

from __future__ import annotations

import json

from modelly.netlogo._names import OBSERVER, Context, Names, Scope, python_name
from modelly.netlogo._syntax import Expr, UntranslatableError

__all__ = ["ATOM", "ExprEmitter"]

ATOM = 10
CONDITIONAL = 0
NOT = 3
COMPARISON = 4
UNARY = 7
PYTHON_OPS = {
    "or": ("or", 1),
    "and": ("and", 2),
    "=": ("==", 4),
    "!=": ("!=", 4),
    "<": ("<", 4),
    ">": (">", 4),
    "<=": ("<=", 4),
    ">=": (">=", 4),
    "+": ("+", 5),
    "-": ("-", 5),
    "*": ("*", 6),
    "/": ("/", 6),
    "mod": ("%", 6),
    "^": ("**", 8),
}
STRICT_LEFT = frozenset({"==", "!=", "<", ">", "<=", ">=", "**"})  # no chaining
# Reporters written the same way in every context: name -> Python template.
TEMPLATES = {
    "random": "self.random_int({0})",
    "random-float": "self.random_float({0})",
    "one-of": "self.one_of({0})",
    "count": "len({0})",
    "abs": "abs({0})",
    "sqrt": "math.sqrt({0})",
    "random-xcor": "self.random_xcor()",
    "random-ycor": "self.random_ycor()",
    "random-pxcor": "self.random_pxcor()",
    "random-pycor": "self.random_pycor()",
    "ticks": "self.ticks",
    "turtles": "self.turtles()",
    "patches": "self.patches",
    "nobody": "None",
    "true": "True",
    "false": "False",
    "world-width": "self.width",
    "world-height": "self.height",
    "min-pxcor": "self.min_pxcor",
    "max-pxcor": "self.max_pxcor",
    "min-pycor": "self.min_pycor",
    "max-pycor": "self.max_pycor",
}
# Reporters that need the running agent: name -> template of its variable.
AGENT_TEMPLATES = {
    "neighbors": "self.neighbors({var})",
    "neighbors4": "self.neighbors4({var})",
    "turtles-here": "self.turtles_here({var})",
    "self": "{var}",
}
PATCH_SETS = frozenset({"patches", "neighbors", "neighbors4", "patch-here"})
TURTLE_SETS = frozenset({"turtles", "turtles-here"})
CONSTANTS = {"nobody": "None", "true": "True", "false": "False"}
HERE = "-here"

Code = tuple[str, int]


def wrap(code: Code, minimum: int) -> str:
    """The text of ``code``, in parentheses when it binds looser than ``minimum``."""
    text, precedence = code
    return text if precedence >= minimum else f"({text})"


def constant(node: Expr) -> str | None:
    """``None``, ``True`` or ``False`` when ``node`` is nobody, true or false."""
    return CONSTANTS.get(node.value) if node.kind == "call" else None


class ExprEmitter:
    """Python expressions for the reporters of one program."""

    def __init__(self, names: Names, breeds: dict[str, str]) -> None:
        """``breeds`` maps each breed's plural name to its Python class."""
        self.names = names
        self.breeds = breeds
        self.counters: dict[str, int] = {}
        self.uses_math = False

    def fresh(self, stem: str, numbered: bool = False) -> str:
        """A new name in the current method: ``turtle``, ``turtle_2``; ``ask_1`` if numbered."""
        count = self.counters.get(stem, 0) + 1
        self.counters[stem] = count
        return stem if count == 1 and not numbered else f"{stem}_{count}"

    def code(self, node: Expr, context: Context, scopes: list[Scope]) -> str:
        """The Python text of ``node``."""
        return self.expr(node, context, scopes)[0]

    def expr(self, node: Expr, context: Context, scopes: list[Scope]) -> Code:
        """The Python text of ``node`` and its precedence.

        Raises:
            UntranslatableError: for a reporter outside the subset or its context.
        """
        if node.kind == "num":
            return repr(node.value), UNARY if node.value < 0 else ATOM
        if node.kind == "str":
            return json.dumps(node.value), ATOM
        if node.kind == "name":
            return self.names.read(node.value, context, scopes), ATOM
        if node.kind == "op":
            return self.operator(node, context, scopes)
        if node.kind == "proc":
            args = [self.code(arg, context, scopes) for arg in node.args]
            return self.call_procedure(node.value, args, context), ATOM
        return self.reporter(node, context, scopes)

    def call_procedure(self, name: str, args: list[str], context: Context) -> str:
        """The call of user procedure ``name``; the translator schedules its body."""
        raise NotImplementedError

    def operator(self, node: Expr, context: Context, scopes: list[Scope]) -> Code:
        """An infix operator, ``with`` filters and comparisons to nobody included."""
        if node.value == "with":
            return self.with_filter(node, context, scopes)
        left, right = (self.expr(arg, context, scopes) for arg in node.args)
        if node.value == "xor":
            return f"bool({wrap(left, 0)}) != bool({wrap(right, 0)})", COMPARISON
        special = constant(node.args[1])
        if node.value in ("=", "!=") and special is not None:
            test = "is" if node.value == "=" else "is not"
            return f"{wrap(left, COMPARISON + 1)} {test} {special}", COMPARISON
        symbol, precedence = PYTHON_OPS[node.value]
        left_minimum = precedence + (symbol in STRICT_LEFT)
        text = f"{wrap(left, left_minimum)} {symbol} {wrap(right, precedence + 1)}"
        return text, precedence

    def with_filter(self, node: Expr, context: Context, scopes: list[Scope]) -> Code:
        """``agents with [condition]`` as a list comprehension."""
        source, condition = node.args
        kind = self.kind_of(source, context, scopes) or "turtle"
        var = self.fresh(kind)
        test = self.code(condition, Context(kind, var, context), scopes)
        agents = self.code(source, context, scopes)
        return f"[{var} for {var} in {agents} if {test}]", ATOM

    def agent(self, context: Context, primitive: str) -> str:
        """The variable of the running agent.

        Raises:
            UntranslatableError: when the observer runs ``primitive``.
        """
        if context.kind == OBSERVER:
            raise UntranslatableError(f"{primitive!r} needs a turtle or a patch")
        return context.var

    def reporter(self, node: Expr, context: Context, scopes: list[Scope]) -> Code:
        """A primitive reporter, a breed's agent set, ``myself`` or ``patch-here``."""
        name = node.value
        if name == "not":
            return f"not {wrap(self.expr(node.args[0], context, scopes), NOT)}", NOT
        args = [self.code(arg, context, scopes) for arg in node.args]
        if name == "any?":
            return f"len({args[0]}) > 0", COMPARISON
        self.uses_math |= name == "sqrt"
        if name in TEMPLATES:
            return TEMPLATES[name].format(*args), ATOM
        if name in AGENT_TEMPLATES:
            return AGENT_TEMPLATES[name].format(var=self.agent(context, name)), ATOM
        return self.agent_reporter(name, context), ATOM

    def agent_reporter(self, name: str, context: Context) -> str:
        """``myself``, ``patch-here``, a breed or the turtles of a breed here."""
        if name == "myself":
            if context.outer is None or context.outer.kind == OBSERVER:
                raise UntranslatableError(
                    "'myself' outside an ask by a turtle or patch"
                )
            return context.outer.var
        if name == "patch-here":
            var = self.agent(context, name)
            return f"{var}.patch" if context.kind == "turtle" else var
        if name in self.breeds:
            return f"self.breed({self.breeds[name]})"
        breed = self.breeds[name.removesuffix(HERE)]
        return f"self.turtles_here({self.agent(context, name)}, {breed})"

    def kind_of(self, node: Expr, context: Context, scopes: list[Scope]) -> str | None:
        """``turtle`` or ``patch`` when ``node`` holds agents of that kind, else None."""
        name = node.value
        if node.kind == "name":
            local = python_name(name)
            found = [scope.kinds[local] for scope in scopes if local in scope.kinds]
            return found[-1] if found else None
        if node.kind == "op":
            return (
                self.kind_of(node.args[0], context, scopes) if name == "with" else None
            )
        if node.kind != "call":
            return None
        if name == "one-of":
            return self.kind_of(node.args[0], context, scopes)
        if name in PATCH_SETS:
            return "patch"
        if name in TURTLE_SETS or name in self.breeds or name.endswith(HERE):
            return "turtle"
        if name == "self":
            return context.kind
        return context.outer.kind if name == "myself" and context.outer else None
