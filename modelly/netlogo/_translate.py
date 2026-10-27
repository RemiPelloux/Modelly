"""From a ``.nlogo`` file to a Python module: a Scenario, agent classes and a model.

The procedures are written as methods of the model, in the order the observer reaches
them from ``setup`` and ``go``: a procedure first called by a turtle takes that turtle
as its argument. ``setup`` runs when the model is created and ``step`` runs ``go``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from modelly.netlogo._emit_stmt import INDENT, Issue, StmtEmitter, is_code, pad
from modelly.netlogo._interface import SECTION, Interface, parse_interface
from modelly.netlogo._module import write_module
from modelly.netlogo._names import (
    OBSERVER,
    Context,
    Names,
    Scope,
    class_name,
    python_name,
)
from modelly.netlogo._parser import parse_program
from modelly.netlogo._syntax import Procedure, Program, Stmt, UntranslatableError

__all__ = ["Translation", "translate"]

ENTRY_POINTS = ("setup", "go")
AGENT_BLOCKS = frozenset({"ask", "create", "hatch", "sprout"})
METHOD_DEPTH = 2


@dataclass
class Translation:
    """The Python source of a translated model and the lines left for a human."""

    source: str
    model_class: str
    issues: list[Issue] = field(default_factory=list)

    @property
    def untranslated(self) -> list[Issue]:
        """The dropped lines that change what the model does (not the display ones)."""
        return [issue for issue in self.issues if not issue.display_only]


def walk(body: tuple[Stmt, ...], into_agents: bool = True) -> Iterator[Stmt]:
    """Every statement of ``body`` and its blocks; ``ask``-like blocks unless told not to."""
    for stmt in body:
        yield stmt
        if into_agents or stmt.kind not in AGENT_BLOCKS:
            for inner in stmt.blocks:
                yield from walk(inner, into_agents)


def dying(program: Program) -> set[str]:
    """The procedures that may run ``die`` on the agent that runs them."""
    dies: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, proc in program.procedures.items():
            kills = any(
                (s.kind == "command" and s.name == "die")
                or (s.kind == "call" and s.name in dies)
                for s in walk(proc.body, into_agents=False)
            )
            if kills and name not in dies:
                dies.add(name)
                changed = True
    return dies


def uses_turtles(program: Program) -> bool:
    """Whether the program has turtles: breeds, turtle variables or created turtles."""
    created = any(
        s.kind in ("create", "hatch", "sprout")
        for p in program.procedures.values()
        for s in walk(p.body)
    )
    return bool(program.breeds or program.turtle_vars or created)


class Translator(StmtEmitter):
    """Writes one program as a Python module."""

    def __init__(self, program: Program, interface: Interface, stem: str) -> None:
        """Name the classes after ``stem`` and index the program's names."""
        sliders = [f.name for f in interface.fields]
        self.program, self.interface = program, interface
        self.title = class_name(stem)
        breeds = {
            plural: class_name(single) for plural, single in program.breeds.items()
        }
        super().__init__(Names(program, sliders), breeds)
        self.turtle_class = f"{self.title}Turtle" if uses_turtles(program) else "None"
        self.setup_statements(program.lines, dying(program))
        self.kinds: dict[str, str] = {}
        self.queue: list[str] = [
            name for name in ENTRY_POINTS if name in program.procedures
        ]
        self.kinds.update((name, OBSERVER) for name in self.queue)

    def call_procedure(self, name: str, args: list[str], context: Context) -> str:
        """``self.proc(agent, *args)``; schedules the procedure for the caller's kind."""
        kind = self.kinds.setdefault(name, context.kind)
        if name not in self.queue:
            self.queue.append(name)
        if kind != OBSERVER and kind != context.kind:
            raise UntranslatableError(
                f"{name!r} is run by a {kind}, here by a {context.kind}"
            )
        agent = [context.var] if kind != OBSERVER else []
        return f"self.{self.names.model(name)}({', '.join([*agent, *args])})"

    def method(self, proc: Procedure) -> list[str]:
        """One procedure as a method of the model."""
        kind = self.kinds.setdefault(proc.name, OBSERVER)
        self.counters, self.procedure = {}, proc.name
        params = [python_name(p) for p in proc.params]
        context = Context(kind, self.fresh(kind)) if kind != OBSERVER else Context()
        agent = [context.var] if kind != OBSERVER else []
        runner = "the observer" if kind == OBSERVER else f"each {kind}"
        word = "to-report" if proc.reporter else "to"
        lines = [
            f"{INDENT}def {self.names.model(proc.name)}({', '.join(['self', *agent, *params])}):",
            f'{pad(METHOD_DEPTH)}"""NetLogo ``{word} {proc.name}``, run by {runner}."""',
        ]
        body = self.block(proc.body, context, [Scope(locals=set(params))], METHOD_DEPTH)
        if body[-1].strip() == "pass" and not any(is_code(line) for line in body[:-1]):
            body = body[:-1]  # the docstring is enough: no `pass`
        return [*lines, *body]

    def methods(self) -> list[str]:
        """Every procedure, reached ones first, each followed by a blank line."""
        lines: list[str] = []
        done = 0
        procedures = self.program.procedures
        while done < len(self.queue) or len(self.queue) < len(procedures):
            if done == len(self.queue):
                self.queue.append(next(n for n in procedures if n not in self.queue))
            lines += ["", *self.method(procedures[self.queue[done]])]
            done += 1
        return lines


def split(text: str) -> tuple[str, str]:
    """The code tab and the interface section of a ``.nlogo`` file."""
    sections = text.split(SECTION)
    return sections[0], sections[1] if len(sections) > 1 else ""


def translate(text: str, stem: str = "model") -> Translation:
    """Translate the ``.nlogo`` source ``text``; ``stem`` names the classes.

    ``"fire"`` gives ``FireModel``, ``FireScenario``, ``FirePatch``. Lines outside the
    subset are kept as ``# NETLOGO`` comments and listed in the translation's issues.
    """
    code, interface_text = split(text)
    interface = parse_interface(interface_text)
    program, skipped = parse_program(code, [f.name for f in interface.fields])
    translator = Translator(program, interface, stem)
    methods = translator.methods()
    for stmt in skipped:
        translator.note(stmt, stmt.name, 0)
    for widget in interface.skipped:
        translator.issues.append(Issue(0, widget, "interface widget not translated"))
    source = write_module(translator, methods)
    return Translation(source, f"{translator.title}Model", translator.issues)
