"""MDL013 and MDL014: the code around a model, its scenarios and its calibration targets.

A Scenario copies its class-level defaults into every instance by reference, so a list,
dict, set or array default is one object that every scenario of the class shares: a
change through one scenario shows up in the others (MDL013).

A calibration ``Target`` reads the model through its ``output`` and ``summary``
functions. A clock or OS entropy read there makes the distance, and so the posterior,
depend on when and where the calibration ran rather than on its seed (MDL014).
"""

from __future__ import annotations

import ast

from modelly.lint.imports import Imports
from modelly.lint.patterns import declared_shared
from modelly.lint.rules import CLOCK_CALLS, ENTROPY_MODULES, dotted, is_mutable_literal

__all__ = ["study_hits"]

Hit = tuple[int, int, str]

SCENARIO_CODE = "MDL013"
TARGET_CODE = "MDL014"
SCENARIO_BASES = frozenset({"Scenario"})
# Calls that build a mutable object: containers and numpy arrays (by their last name).
MUTABLE_BUILDERS = frozenset(
    {"defaultdict", "deque", "Counter", "OrderedDict", "bytearray"}
    | {"array", "zeros", "ones", "full", "empty", "arange", "linspace"}
)
CALIBRATE = "modelly.calibrate"
TARGET = "Target"
# Timers are fine in a model (profiling) but a target built on one is a measure of the machine.
TIMERS = frozenset(
    f"time.{name}{suffix}"
    for name in ("perf_counter", "monotonic", "process_time", "thread_time")
    for suffix in ("", "_ns")
)


def is_mutable_default(node: ast.AST | None) -> bool:
    """Whether ``node`` is a mutable literal or a call that builds a container or array."""
    if is_mutable_literal(node):
        return True
    return (
        isinstance(node, ast.Call)
        and (dotted(node.func) or [""])[-1] in MUTABLE_BUILDERS
    )


def scenario_defaults(node: ast.ClassDef) -> list[ast.AnnAssign]:
    """The annotated fields of a Scenario subclass whose default is mutable.

    Only annotated, public names are Scenario fields; ``ClassVar`` is shared on purpose.
    """
    return [
        statement
        for statement in node.body
        if isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and not statement.target.id.startswith("_")
        and is_mutable_default(statement.value)
        and not declared_shared(statement)
    ]


def scenario_hits(tree: ast.AST) -> set[Hit]:
    """MDL013 for every Scenario subclass, including subclasses of local ones."""
    classes = sorted(
        (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)),
        key=lambda node: (node.lineno, node.col_offset),
    )
    scenarios = set(SCENARIO_BASES)
    hits: set[Hit] = set()
    for node in classes:
        if not any((dotted(base) or [""])[-1] in scenarios for base in node.bases):
            continue
        scenarios.add(node.name)
        hits |= {
            (field.lineno, field.col_offset + 1, SCENARIO_CODE)
            for field in scenario_defaults(node)
        }
    return hits


def module_imports(tree: ast.AST) -> Imports:
    """Every import of the module, wherever it is, for resolving call names."""
    imports = Imports()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            imports.add(node)
    return imports


def reads_clock(name: str) -> bool:
    """Whether the resolved call ``name`` reads a clock, a timer or OS entropy."""
    return (
        name in CLOCK_CALLS
        or name in TIMERS
        or name.split(".", maxsplit=1)[0] in ENTROPY_MODULES
    )


def clock_calls(node: ast.AST, imports: Imports) -> set[Hit]:
    """MDL014 at every clock read under ``node``."""
    return {
        (call.lineno, call.col_offset + 1, TARGET_CODE)
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and reads_clock(imports.resolve(call.func) or "")
    }


def target_hits(tree: ast.Module) -> set[Hit]:
    """MDL014 in the arguments of ``Target(...)`` and the module functions they name."""
    imports = module_imports(tree)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    hits: set[Hit] = set()
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        name = imports.resolve(call.func) or ""
        if not (name.startswith(CALIBRATE) and name.endswith(f".{TARGET}")):
            continue
        for value in (*call.args, *(keyword.value for keyword in call.keywords)):
            hits |= clock_calls(value, imports)
            if isinstance(value, ast.Name) and value.id in functions:
                hits |= clock_calls(functions[value.id], imports)
    return hits


def study_hits(tree: ast.Module) -> set[Hit]:
    """The MDL013 and MDL014 hits of one parsed module."""
    return scenario_hits(tree) | target_hits(tree)
