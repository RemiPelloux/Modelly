"""A ``modelly lint`` rule: EXP001, ``print()`` in a model's code."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass

from modelly.lint import Rule


def prints(tree: ast.Module) -> Iterator[tuple[int, int]]:
    """``(line, column)`` of every call to the built-in ``print``."""
    for node in ast.walk(tree):
        called = isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        if called and node.func.id == "print":
            yield node.lineno, node.col_offset


@dataclass(frozen=True)
class PluginRule:
    """What a ``modelly.lint_rules`` entry point names: a rule and its check."""

    rule: Rule
    check: object


NO_PRINT = PluginRule(
    Rule(
        "EXP001",
        "warning",
        "print() in model code",
        "record values with a DataCollector, or log them with modelly.log",
    ),
    prints,
)
