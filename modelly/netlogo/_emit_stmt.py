"""Writing NetLogo commands as Python statements.

``ask agents [ ... ]`` becomes a nested function run by ``self.ask(agents, fn)``, so
``die`` and ``stop`` are a ``return`` from the agent's own code, as in NetLogo. A
command outside the subset becomes a ``# NETLOGO`` comment and an entry in the report.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from modelly.netlogo._emit_expr import ATOM, ExprEmitter, wrap
from modelly.netlogo._names import OBSERVER, Context, Scope, python_name
from modelly.netlogo._syntax import Stmt, UntranslatableError

__all__ = ["INDENT", "Issue", "StmtEmitter"]

INDENT = "    "
Emit = Callable[[Stmt, Context, list[Scope], int], list[str]]
AND_OPERAND = 3  # binds tighter than `and`
GO = "go"
# Turtle commands: NetLogo name -> Python method of the turtle (inputs in order).
TURTLE_METHODS = {
    "fd": "forward",
    "forward": "forward",
    "rt": "right",
    "right": "right",
    "lt": "left",
    "left": "left",
    "setxy": "setxy",
    "move-to": "move_to_agent",
}
BACKWARD = frozenset({"bk", "back"})
MODEL_METHODS = {
    "clear-all": "clear_all",
    "ca": "clear_all",
    "reset-ticks": "reset_ticks",
    "tick": "tick",
}


@dataclass(frozen=True)
class Issue:
    """A line of the NetLogo source the translation dropped, and why."""

    line: int
    text: str
    reason: str
    display_only: bool = False


def pad(depth: int) -> str:
    """The indentation of ``depth`` levels."""
    return INDENT * depth


def is_code(line: str) -> bool:
    """Whether ``line`` is a statement rather than a comment or a blank line."""
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


class StmtEmitter(ExprEmitter):
    """Python statements for the commands of one program."""

    turtle_class: str  # the generated turtle class, "None" when the program has none

    def setup_statements(self, lines: list[str], dies: set[str]) -> None:
        """Keep the NetLogo source lines and the procedures that may kill their turtle."""
        self.source = lines
        self.dies = dies
        self.issues: list[Issue] = []
        self.procedure = ""

    def block(
        self, body: tuple[Stmt, ...], context: Context, scopes: list[Scope], depth: int
    ) -> list[str]:
        """The statements of ``body`` at ``depth``; ``pass`` when it has none."""
        lines: list[str] = []
        for stmt in body:
            lines.extend(self.statement_or_note(stmt, context, scopes, depth))
        while lines and not lines[0].strip():
            lines.pop(0)
        if not any(is_code(line) for line in lines):
            lines.append(pad(depth) + "pass")
        return lines

    def note(self, stmt: Stmt, reason: str, depth: int, display: bool = False) -> str:
        """A comment for a dropped line, recorded in the report."""
        text = (
            self.source[stmt.line - 1].strip()
            if 0 < stmt.line <= len(self.source)
            else ""
        )
        self.issues.append(Issue(stmt.line, text, reason, display))
        label = "display only, dropped" if display else f"not translated ({reason})"
        return f"{pad(depth)}# NETLOGO line {stmt.line}, {label}: {text}"

    def statement_or_note(
        self, stmt: Stmt, context: Context, scopes: list[Scope], depth: int
    ) -> list[str]:
        """The statement, or a comment when it cannot be translated."""
        if stmt.kind == "untranslated":
            return [self.note(stmt, stmt.name, depth)]
        if stmt.kind == "display":
            return [self.note(stmt, "display", depth, display=True)]
        try:
            emit: Emit = getattr(self, f"emit_{stmt.kind}")
            return emit(stmt, context, scopes, depth)
        except UntranslatableError as error:
            return [self.note(stmt, str(error), depth)]

    def emit_set(
        self, stmt: Stmt, context: Context, scopes: list[Scope], depth: int
    ) -> list[str]:
        """``set x value``."""
        value = self.code(stmt.args[0], context, scopes)
        return [f"{pad(depth)}{self.names.write(stmt.name, context, scopes)} = {value}"]

    def emit_let(
        self, stmt: Stmt, context: Context, scopes: list[Scope], depth: int
    ) -> list[str]:
        """``let x value``: a local of the current function."""
        value = self.code(stmt.args[0], context, scopes)
        local = python_name(stmt.name)
        scopes[-1].locals.add(local)
        kind = self.kind_of(stmt.args[0], context, scopes)
        if kind:
            scopes[-1].kinds[local] = kind
        return [f"{pad(depth)}{local} = {value}"]

    def emit_if(
        self, stmt: Stmt, context: Context, scopes: list[Scope], depth: int
    ) -> list[str]:
        """``if c [ ... ]``; a lone nested ``if`` joins with ``and``."""
        tests, body = [stmt.args[0]], stmt.blocks[0]
        while len(body) == 1 and body[0].kind == "if":
            tests.append(body[0].args[0])
            body = body[0].blocks[0]
        codes = [self.expr(test, context, scopes) for test in tests]
        test = (
            codes[0][0]
            if len(codes) == 1
            else " and ".join(wrap(c, AND_OPERAND) for c in codes)
        )
        return [
            f"{pad(depth)}if {test}:",
            *self.block(body, context, scopes, depth + 1),
        ]

    def emit_ifelse(
        self, stmt: Stmt, context: Context, scopes: list[Scope], depth: int
    ) -> list[str]:
        """``ifelse c [ ... ] [ ... ]``; two assignments to one variable as a ternary."""
        test = self.expr(stmt.args[0], context, scopes)
        then, otherwise = stmt.blocks
        if self.same_assignment(then, otherwise):
            target = self.names.write(then[0].name, context, scopes)
            first, second = (
                self.expr(b[0].args[0], context, scopes) for b in (then, otherwise)
            )
            ternary = f"{wrap(first, 1)} if {wrap(test, 1)} else {wrap(second, 1)}"
            return [f"{pad(depth)}{target} = {ternary}"]
        lines = [
            f"{pad(depth)}if {test[0]}:",
            *self.block(then, context, scopes, depth + 1),
        ]
        return [
            *lines,
            f"{pad(depth)}else:",
            *self.block(otherwise, context, scopes, depth + 1),
        ]

    @staticmethod
    def same_assignment(then: tuple[Stmt, ...], otherwise: tuple[Stmt, ...]) -> bool:
        """Whether both branches are a single ``set`` of the same variable."""
        pair = (*then, *otherwise)
        return (
            len(then) == len(otherwise) == 1
            and all(s.kind == "set" for s in pair)
            and then[0].name == otherwise[0].name
        )

    def emit_repeat(
        self, stmt: Stmt, context: Context, scopes: list[Scope], depth: int
    ) -> list[str]:
        """``repeat n [ ... ]``."""
        count = stmt.args[0]
        times = (
            repr(count.value)
            if count.kind == "num" and isinstance(count.value, int)
            else f"int({self.code(count, context, scopes)})"
        )
        return [
            f"{pad(depth)}for _ in range({times}):",
            *self.block(stmt.blocks[0], context, scopes, depth + 1),
        ]

    def closure(
        self,
        kind: str,
        body: tuple[Stmt, ...],
        context: Context,
        scopes: list[Scope],
        depth: int,
    ) -> tuple[str, list[str]]:
        """A nested function running ``body`` as one agent of ``kind``: name and lines."""
        var, name = self.fresh(kind), self.fresh("ask", numbered=True)
        scope = Scope()
        lines = self.block(
            body, Context(kind, var, context), [*scopes, scope], depth + 1
        )
        head = ["", f"{pad(depth)}def {name}({var}):"]
        if scope.nonlocals:
            head.append(
                f"{pad(depth + 1)}nonlocal {', '.join(sorted(scope.nonlocals))}"
            )
        return name, [*head, *lines, ""]

    def emit_ask(
        self, stmt: Stmt, context: Context, scopes: list[Scope], depth: int
    ) -> list[str]:
        """``ask agents [ ... ]``: each agent, in random order, runs the block."""
        kind = self.kind_of(stmt.args[0], context, scopes) or "turtle"
        agents = self.code(stmt.args[0], context, scopes)
        name, lines = self.closure(kind, stmt.blocks[0], context, scopes, depth)
        return [*lines, f"{pad(depth)}self.ask({agents}, {name})"]

    def creation(self, stmt: Stmt, context: Context, count: str) -> str:
        """The call creating the turtles of ``create``, ``hatch`` or ``sprout``."""
        breed = self.breeds.get(stmt.name, "")
        if stmt.kind == "create":
            return f"self.create({breed or self.turtle_class}, {count})"
        var = self.agent(context, stmt.kind)
        if (stmt.kind == "hatch") != (context.kind == "turtle"):
            raise UntranslatableError(f"{stmt.kind!r} run by a {context.kind}")
        return f"self.{stmt.kind}({var}, {count}{', ' + breed if breed else ''})"

    def emit_create(
        self, stmt: Stmt, context: Context, scopes: list[Scope], depth: int
    ) -> list[str]:
        """``create-turtles``, ``hatch`` or ``sprout``, then the block for each new turtle."""
        call = self.creation(stmt, context, self.code(stmt.args[0], context, scopes))
        if not stmt.blocks:
            return [pad(depth) + call]
        name, lines = self.closure("turtle", stmt.blocks[0], context, scopes, depth)
        return [*lines, f"{pad(depth)}self.ask({call}, {name})"]

    emit_hatch = emit_create
    emit_sprout = emit_create

    def emit_report(
        self, stmt: Stmt, context: Context, scopes: list[Scope], depth: int
    ) -> list[str]:
        """``report value``."""
        return [f"{pad(depth)}return {self.code(stmt.args[0], context, scopes)}"]

    def emit_call(
        self, stmt: Stmt, context: Context, scopes: list[Scope], depth: int
    ) -> list[str]:
        """A user command; when it may kill the turtle, the rest of its code is skipped."""
        args = [self.code(arg, context, scopes) for arg in stmt.args]
        lines = [pad(depth) + self.call_procedure(stmt.name, args, context)]
        if stmt.name in self.dies and context.kind == "turtle":
            lines += [
                f"{pad(depth)}if not {context.var}.alive:",
                f"{pad(depth + 1)}return",
            ]
        return lines

    def emit_command(
        self, stmt: Stmt, context: Context, scopes: list[Scope], depth: int
    ) -> list[str]:
        """A primitive command: the model's, the turtle's, ``die`` or ``stop``."""
        name, args = stmt.name, [self.expr(arg, context, scopes) for arg in stmt.args]
        if name in MODEL_METHODS:
            return [f"{pad(depth)}self.{MODEL_METHODS[name]}()"]
        if name == "stop":
            last = (
                ["self.running = False"]
                if context.kind == OBSERVER and self.procedure == GO
                else []
            )
            return [pad(depth) + line for line in (*last, "return")]
        if context.kind != "turtle":
            raise UntranslatableError(f"{name!r} needs a turtle")
        if name == "die":
            return [f"{pad(depth)}{context.var}.die()", f"{pad(depth)}return"]
        if name in BACKWARD:
            return [f"{pad(depth)}{context.var}.forward(-{wrap(args[0], ATOM)})"]
        inputs = ", ".join(text for text, _ in args)
        return [f"{pad(depth)}{context.var}.{TURTLE_METHODS[name]}({inputs})"]
