"""Lint rules from other packages: the ``modelly.lint_rules`` entry-point group.

An entry point names an object with two attributes: ``rule``, a :class:`Rule` whose
code is not one of Modelly's, and ``check(tree)``, which takes the parsed module
(``ast.Module``) and yields the ``(line, column)`` of every hit. ``# noqa`` and the
``[tool.modelly.lint]`` selection apply to plugin codes as to built-in ones.

A plugin that fails to load, lacks either attribute or reuses a built-in code is left
out with a ``RuntimeWarning`` naming it; the other rules still run. Plugins are read
once per process (``plugin_rules.cache_clear()`` reads them again).
"""

from __future__ import annotations

import ast
import functools
import warnings
from typing import Any

from modelly.lint.rules import RULES, Rule
from modelly.plugins import load_all

GROUP = "modelly.lint_rules"


def _usable(name: str, rule: Any) -> bool:
    """Whether the loaded object can run as a rule; warn when it cannot."""
    problem = None
    if not isinstance(getattr(rule, "rule", None), Rule) or not callable(
        getattr(rule, "check", None)
    ):
        problem = "has no Rule as .rule and check(tree) as .check"
    elif rule.rule.code in RULES:
        problem = f"reuses the built-in code {rule.rule.code}"
    if problem is not None:
        warnings.warn(f"lint plugin {name!r} {problem}; skipped", RuntimeWarning, 3)
    return problem is None


@functools.cache
def plugin_rules() -> dict[str, Any]:
    """The usable plugin rules, by code."""
    loaded, errors = load_all(GROUP)
    for error in errors.values():
        warnings.warn(f"{error}; skipped", RuntimeWarning, stacklevel=2)
    return {
        rule.rule.code: rule for name, rule in loaded.items() if _usable(name, rule)
    }


def all_rules() -> dict[str, Rule]:
    """The built-in rules, then the plugin rules, by code."""
    return {**RULES, **{code: plugin.rule for code, plugin in plugin_rules().items()}}


def plugin_hits(tree: ast.Module) -> set[tuple[int, int, str]]:
    """``(line, column, code)`` of every plugin rule's hit in ``tree``."""
    return {
        (line, column, code)
        for code, plugin in plugin_rules().items()
        for line, column in plugin.check(tree)
    }
