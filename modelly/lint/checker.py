"""The AST visitor behind ``modelly.lint``: one pass per module, findings as (line, col, code)."""

from __future__ import annotations

import ast

from modelly.lint.imports import Imports
from modelly.lint.patterns import (
    column_names,
    declared_shared,
    is_global_random,
    removed_in_loop,
    sorts_by_id,
    writes_columns_only,
)
from modelly.lint.rules import (
    AGENT_BASES,
    CLOCK_CALLS,
    ENTROPY_MODULES,
    FRAME_BUILDERS,
    MODEL_BASES,
    MUTATORS,
    SCANS,
    STEP_COMPLEXITY_LIMIT,
    branches,
    calls_super_init,
    is_mutable_literal,
    is_population,
    is_set_expr,
)

Hit = tuple[int, int, str]


class Checker(ast.NodeVisitor):
    """Collect rule hits for one module."""

    def __init__(self, imported_columns: frozenset[str] = frozenset()) -> None:
        """Start with no imports seen, outside any class, function or loop.

        ``imported_columns`` are the Column attributes of agent classes the module
        imports from other files (see ``modelly.lint.siblings``).
        """
        self.hits: set[Hit] = set()
        self.kinds: dict[
            str, str
        ] = {}  # class name -> "agent" | "model", for local subclasses
        self.kind: str | None = None  # the kind of the class being visited
        self.function: str | None = None
        self.population_depth = 0
        self.imports = Imports()
        self.imported_columns = imported_columns
        self.columns: set[str] = set()  # Column attributes declared here or imported

    def hit(self, node: ast.AST, code: str) -> None:
        """Record ``code`` at ``node``."""
        self.hits.add((node.lineno, node.col_offset + 1, code))

    # The module, imports and globals.

    def visit_Module(self, node: ast.Module) -> None:  # noqa: D102
        self.columns = column_names(node) | self.imported_columns
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:  # noqa: D102
        self.imports.add(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: D102
        self.imports.add(node)

    def visit_Global(self, node: ast.Global) -> None:  # noqa: D102
        if self.kind and self.function:
            self.hit(node, "MDL008")

    # Classes and functions: where we are decides which rules apply.

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: D102
        kind = self.class_kind(node)
        if kind:
            self.kinds[node.name] = kind
        if kind == "agent":
            self.check_class_attributes(node)
        outer, self.kind = self.kind, kind
        self.generic_visit(node)
        self.kind = outer

    def class_kind(self, node: ast.ClassDef) -> str | None:
        """Return "agent" or "model" when a base class is one, directly or through this module."""
        for base in node.bases:
            name = (
                base.attr
                if isinstance(base, ast.Attribute)
                else getattr(base, "id", "")
            )
            if name in AGENT_BASES:
                return "agent"
            if name in MODEL_BASES:
                return "model"
            if name in self.kinds:
                return self.kinds[name]
        return None

    def check_class_attributes(self, node: ast.ClassDef) -> None:
        """MDL004: a list, dict or set in an agent's class body is one object for all agents.

        ``__slots__`` and attributes annotated ``ClassVar`` are shared on purpose.
        """
        for statement in node.body:
            value = (
                statement.value
                if isinstance(statement, ast.Assign | ast.AnnAssign)
                else None
            )
            if is_mutable_literal(value) and not declared_shared(statement):
                self.hit(statement, "MDL004")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: D102
        if self.kind and node.name == "__init__" and not calls_super_init(node):
            self.hit(node, "MDL002")
        if self.kind and node.name == "step" and branches(node) > STEP_COMPLEXITY_LIMIT:
            self.hit(node, "MDL105")
        outer, self.function = self.function, node.name
        depth, self.population_depth = self.population_depth, 0
        self.generic_visit(node)
        self.function, self.population_depth = outer, depth

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: D102
        self.visit_FunctionDef(node)

    # Loops: sets, population scans and nested population loops.

    def visit_For(self, node: ast.For) -> None:  # noqa: D102
        self.visit(node.iter)
        if self.kind == "model" and self.is_activation_loop(node):
            self.hit(node, "MDL103")
        self.check_population_loop(node)
        self.visit_loop(node, node.iter, [node.target, *node.body, *node.orelse])

    def is_activation_loop(self, node: ast.For) -> bool:
        """MDL103: ``for a in self.agents: a.step()`` and nothing else."""
        if not (is_population(node.iter, True) and len(node.body) == 1):
            return False
        call = node.body[0].value if isinstance(node.body[0], ast.Expr) else None
        return (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "step"
            and isinstance(call.func.value, ast.Name)
            and isinstance(node.target, ast.Name)
            and call.func.value.id == node.target.id
        )

    def check_population_loop(self, node: ast.For) -> None:
        """MDL007 and MDL107: what the body of a loop over the population does."""
        if not is_population(node.iter, self.kind == "model"):
            return
        if removed_in_loop(node):
            self.hit(node, "MDL007")
        if self.kind == "model" and writes_columns_only(node, self.columns):
            self.hit(node, "MDL107")

    def visit_loop(self, node: ast.AST, iterable: ast.AST, body: list[ast.AST]) -> None:
        """Check ``iterable`` and visit ``body`` one population level deeper when it is one."""
        if is_set_expr(iterable):
            self.hit(node, "MDL003")
        scans = is_population(iterable, self.kind == "model")
        if scans:
            self.check_scan(node)
        self.population_depth += scans
        for child in body:
            self.visit(child)
        self.population_depth -= scans

    def check_scan(self, node: ast.AST) -> None:
        """MDL101 inside an agent, MDL102 when already inside a population loop."""
        if self.kind == "agent":
            self.hit(node, "MDL101")
        elif self.population_depth:
            self.hit(node, "MDL102")

    def visit_comprehension_node(self, node: ast.AST) -> None:
        """Comprehensions loop too: each generator is one level."""
        generators = node.generators
        self.visit(generators[0].iter)
        first = generators[0]
        rest = [*first.ifs, *generators[1:], *self.comprehension_bodies(node)]
        self.visit_loop(node, first.iter, rest)

    @staticmethod
    def comprehension_bodies(node: ast.AST) -> list[ast.AST]:
        """The element expressions of a list, set, dict or generator comprehension."""
        if isinstance(node, ast.DictComp):
            return [node.key, node.value]
        return [node.elt]

    def visit_ListComp(self, node: ast.ListComp) -> None:  # noqa: D102
        self.visit_comprehension_node(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:  # noqa: D102
        self.visit_comprehension_node(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:  # noqa: D102
        self.visit_comprehension_node(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:  # noqa: D102
        self.visit_comprehension_node(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:  # noqa: D102
        self.visit(node.iter)
        self.visit_loop(node.iter, node.iter, [*node.ifs])

    # Calls: generators, clocks, AgentSet scans and changes, deepcopy, pandas.

    def visit_Call(self, node: ast.Call) -> None:  # noqa: D102
        for code in self.call_codes(node):
            self.hit(node, code)
        self.generic_visit(node)

    def call_codes(self, node: ast.Call) -> list[str]:
        """The rules ``node`` breaks, from its resolved name and where it is."""
        name = self.imports.resolve(node.func) or ""
        in_model = self.kind == "model"
        func = node.func
        method = func.attr if isinstance(func, ast.Attribute) else None
        owner = func.value if isinstance(func, ast.Attribute) else None
        checks = {
            "MDL001": is_global_random(name, node),
            "MDL005": bool(self.kind)
            and (name in CLOCK_CALLS or name.split(".")[0] in ENTROPY_MODULES),
            "MDL006": sorts_by_id(node) or self.hashes(func),
            "MDL009": method in MUTATORS
            and not isinstance(owner, ast.Call)
            and is_population(owner, in_model),
            "MDL101": method in SCANS
            and self.kind == "agent"
            and is_population(owner, False),
            "MDL104": self.function == "step" and self.is_deepcopy(func),
            "MDL106": self.function == "step" and name in FRAME_BUILDERS,
        }
        return [code for code, broken in checks.items() if broken]

    def hashes(self, func: ast.AST) -> bool:
        """MDL006: the builtin ``hash()`` in model code, outside ``__hash__``."""
        return (
            bool(self.kind)
            and isinstance(func, ast.Name)
            and func.id == "hash"
            and self.function != "__hash__"
        )

    @staticmethod
    def is_deepcopy(func: ast.AST) -> bool:
        """Whether ``func`` names ``deepcopy`` or ``copy.deepcopy``."""
        if isinstance(func, ast.Name):
            return func.id == "deepcopy"
        return isinstance(func, ast.Attribute) and func.attr == "deepcopy"
