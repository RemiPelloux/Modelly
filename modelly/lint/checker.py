"""The AST visitor behind ``modelly.lint``: one pass per module, findings as (line, col, code)."""

from __future__ import annotations

import ast

from modelly.lint.rules import (
    AGENT_BASES,
    MODEL_BASES,
    NUMPY_SEEDED,
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

    def __init__(self) -> None:
        """Start with no imports seen, outside any class, function or loop."""
        self.hits: set[Hit] = set()
        self.kinds: dict[
            str, str
        ] = {}  # class name -> "agent" | "model", for local subclasses
        self.kind: str | None = None  # the kind of the class being visited
        self.function: str | None = None
        self.population_depth = 0
        self.random_modules: set[str] = set()  # names bound to the stdlib random module
        self.random_functions: set[str] = set()  # names imported from it
        self.numpy_modules: set[str] = set()  # names bound to numpy
        self.numpy_random: set[str] = set()  # names bound to numpy.random

    def hit(self, node: ast.AST, code: str) -> None:
        """Record ``code`` at ``node``."""
        self.hits.add((node.lineno, node.col_offset + 1, code))

    # Imports: which local names reach a global random generator.

    def visit_Import(self, node: ast.Import) -> None:  # noqa: D102
        for alias in node.names:
            bound = alias.asname or alias.name
            if alias.name == "random":
                self.random_modules.add(bound)
            elif alias.name == "numpy":
                self.numpy_modules.add(bound)
            elif alias.name == "numpy.random":
                self.numpy_random.add(alias.asname or "numpy.random")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: D102
        for alias in node.names:
            bound = alias.asname or alias.name
            if node.module == "random" and alias.name not in {"Random", "SystemRandom"}:
                self.random_functions.add(bound)
            elif node.module == "numpy" and alias.name == "random":
                self.numpy_random.add(bound)
            elif node.module == "numpy.random" and alias.name not in NUMPY_SEEDED:
                self.random_functions.add(bound)

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
        """MDL004: a list, dict or set in an agent's class body is one object for all agents."""
        for statement in node.body:
            value = (
                statement.value
                if isinstance(statement, ast.Assign | ast.AnnAssign)
                else None
            )
            if is_mutable_literal(value):
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

    # Calls: global random generators, AgentSet scans, deepcopy.

    def visit_Call(self, node: ast.Call) -> None:  # noqa: D102
        if self.is_global_random(node.func, node):
            self.hit(node, "MDL001")
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in SCANS
            and self.kind == "agent"
            and is_population(func.value, False)
        ):
            self.hit(node, "MDL101")
        if self.function == "step" and self.is_deepcopy(func):
            self.hit(node, "MDL104")
        self.generic_visit(node)

    def is_global_random(self, func: ast.AST, call: ast.Call) -> bool:
        """MDL001: random.x(), numpy.random.x(), or numpy.random.default_rng() with no seed."""
        if isinstance(func, ast.Name):
            return func.id in self.random_functions and not (
                func.id == "default_rng" and call.args
            )
        if not isinstance(func, ast.Attribute):
            return False
        owner = func.value
        if func.attr == "default_rng":
            return not call.args and self.is_numpy_random(owner)
        if func.attr in NUMPY_SEEDED or func.attr in {"Random", "SystemRandom"}:
            return False
        return (
            isinstance(owner, ast.Name) and owner.id in self.random_modules
        ) or self.is_numpy_random(owner)

    def is_numpy_random(self, node: ast.AST) -> bool:
        """Whether ``node`` is ``np.random`` or a name bound to numpy.random."""
        if isinstance(node, ast.Name):
            return node.id in self.numpy_random
        return (
            isinstance(node, ast.Attribute)
            and node.attr == "random"
            and isinstance(node.value, ast.Name)
            and node.value.id in self.numpy_modules
        )

    @staticmethod
    def is_deepcopy(func: ast.AST) -> bool:
        """Whether ``func`` names ``deepcopy`` or ``copy.deepcopy``."""
        if isinstance(func, ast.Name):
            return func.id == "deepcopy"
        return isinstance(func, ast.Attribute) and func.attr == "deepcopy"
