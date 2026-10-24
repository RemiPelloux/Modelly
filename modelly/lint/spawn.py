"""MDL010: objects handed to worker processes that a ``spawn`` worker cannot import.

Windows and macOS start process-pool workers with ``spawn``: each worker imports the
function or class it runs by its module and qualified name. A lambda, or a function or
class defined inside another function (a closure), has no such name, so the run fails
there even when it works on Linux, where workers are forked.
"""

from __future__ import annotations

import ast

from modelly.lint.rules import dotted

Hit = tuple[int, int, str]

CODE = "MDL010"
# functools.partial(f, ...) is importable exactly when f is.
WRAPPERS = frozenset({"partial"})
# Calls whose every argument is sent to worker processes.
SPAWN_CALLS = frozenset(
    {"run_batch", "run_grid", "run_scenarios", "Experiment", "RunConfiguration"}
)
# Keyword arguments of any call that name what a worker builds or runs.
FACTORY_KEYWORDS = frozenset({"model_class", "model_cls", "run"})
FACTORY_SUFFIX = "factory"
INLINE_WORKERS = 1  # workers=1 runs in this process: nothing is sent anywhere


def is_factory_keyword(name: str | None) -> bool:
    """Whether a keyword argument names a model factory, class or run function."""
    return bool(name) and (name in FACTORY_KEYWORDS or name.endswith(FACTORY_SUFFIX))


def runs_inline(call: ast.Call) -> bool:
    """Whether ``call`` passes ``workers=1``, which runs every task in this process."""
    return any(
        k.arg == "workers"
        and isinstance(k.value, ast.Constant)
        and k.value.value == INLINE_WORKERS
        for k in call.keywords
    )


class SpawnChecker(ast.NodeVisitor):
    """Collect MDL010 hits: lambdas and nested definitions passed to process pools."""

    def __init__(self) -> None:
        """Start at module level, where every definition is importable."""
        self.hits: set[Hit] = set()
        self.local_names: list[set[str]] = []  # one set per enclosing function

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: D102
        self.define(node.name)
        self.local_names.append(set())
        self.generic_visit(node)
        self.local_names.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: D102
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: D102
        self.define(node.name)
        self.generic_visit(node)

    def define(self, name: str) -> None:
        """Record ``name`` as nested when it is defined inside a function."""
        if self.local_names:
            self.local_names[-1].add(name)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: D102
        callee = (dotted(node.func) or [""])[-1]
        if runs_inline(node):
            callee = ""
        sent = list(node.args) if callee in SPAWN_CALLS else []
        sent += [
            k.value
            for k in node.keywords
            if callee in SPAWN_CALLS or is_factory_keyword(k.arg)
        ]
        for value in sent:
            self.check(value)
        self.generic_visit(node)

    def check(self, value: ast.AST) -> None:
        """Report ``value`` when it, or an element of a literal holding it, is not importable."""
        if isinstance(value, ast.Lambda) or self.is_nested(value):
            self.hits.add((value.lineno, value.col_offset + 1, CODE))
        elif isinstance(value, ast.List | ast.Tuple | ast.Set):
            for element in value.elts:
                self.check(element)
        elif isinstance(value, ast.Dict):
            for element in value.values:
                self.check(element)
        elif (
            isinstance(value, ast.Call) and (dotted(value.func) or [""])[-1] in WRAPPERS
        ):
            for element in value.args[:1]:
                self.check(element)

    def is_nested(self, value: ast.AST) -> bool:
        """Whether ``value`` names a function or class defined inside an enclosing function."""
        return isinstance(value, ast.Name) and any(
            value.id in names for names in self.local_names
        )


def spawn_hits(tree: ast.AST) -> set[Hit]:
    """The MDL010 hits of one parsed module."""
    checker = SpawnChecker()
    checker.visit(tree)
    return checker.hits
