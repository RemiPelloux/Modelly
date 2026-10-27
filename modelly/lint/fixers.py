"""The safe fixes behind ``modelly lint --fix``: MDL001, MDL002, MDL003, MDL009 and MDL011.

``FixCollector`` is the linter's own visitor, so a fix is computed for exactly the node a
finding points at. A fixer returns None when the rewrite is not unambiguous; the finding
then stays for a person to fix. Every fix removes its own finding, so a second run
changes nothing.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from typing import Any

from modelly.lint.checker import Checker, Hit
from modelly.lint.edits import Edit, Located, Source
from modelly.lint.patterns import FROZEN_DRAW, QMC_MODULE, SAMPLER_SEEDS
from modelly.lint.rules import dotted, is_set_expr

# random.Random methods the model's FastRandom (self.random) has, same signature.
STDLIB_DRAWS = frozenset(
    {
        *("random", "uniform", "randint", "randrange", "choice", "choices"),
        *("shuffle", "sample", "gauss", "normalvariate", "expovariate"),
        *("betavariate", "gammavariate", "lognormvariate", "triangular"),
        *("vonmisesvariate", "paretovariate", "weibullvariate", "getrandbits"),
        "binomialvariate",
    }
)
# numpy.random functions whose numpy Generator (self.rng) method takes the same arguments.
NUMPY_DRAWS = frozenset(
    {
        *("random", "normal", "uniform", "choice", "shuffle", "permutation"),
        *("exponential", "poisson", "binomial", "beta", "gamma", "lognormal"),
        *("geometric", "standard_normal", "multinomial", "dirichlet", "laplace"),
        *("logistic", "negative_binomial", "triangular", "weibull", "pareto"),
        "chisquare",
    }
)
# Base class -> the __init__ parameters passed on to it, in order.
SUPER_ARGS = {
    "Agent": ("model",),
    "CellAgent": ("model",),
    "FixedAgent": ("model",),
    "ContinuousSpaceAgent": ("space", "model"),
}
MODEL_KEYWORDS = ("rng", "scenario")  # Model.__init__ takes one of them, not both
AGENT_KEY = ", key=lambda a: a.unique_id"  # agents do not compare; their ids do
SIMPLE = ast.Name | ast.Attribute | ast.Subscript | ast.Call
MODEL_GENERATOR = "self.rng"  # the model's numpy Generator, which qmc and scipy accept


class FixCollector(Checker):
    """The linter's visitor, also recording a fix for each fixable hit."""

    def __init__(self, source: Source) -> None:
        """Visit ``source`` with no imported columns (no fix depends on them)."""
        super().__init__()
        self.source = source
        self.classes: list[ast.ClassDef] = []
        self.functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self.fixes: list[tuple[Hit, Edit]] = []

    def hit(self, node: Located, code: str) -> None:
        """Record the hit and, when the rule has a safe fix here, the edit."""
        super().hit(node, code)
        fixer = FIXERS.get(code)
        edit = fixer(self, node) if fixer else None
        if edit is not None:
            self.fixes.append(((node.lineno, node.col_offset + 1, code), edit))

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: D102
        self.classes.append(node)
        super().visit_ClassDef(node)
        self.classes.pop()

    def visit_FunctionDef(  # noqa: D102
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        self.functions.append(node)
        super().visit_FunctionDef(node)
        self.functions.pop()

    def in_method(self) -> bool:
        """Whether the innermost function is a method of an agent or model (has ``self``)."""
        if not (self.kind and self.functions):
            return False
        args = self.functions[-1].args
        return bool(args.args) and args.args[0].arg == "self"


def fix_random(collector: FixCollector, node: ast.Call) -> Edit | None:
    """MDL001: ``random.choice(x)`` -> ``self.random.choice(x)``; numpy -> ``self.rng``."""
    if not collector.in_method():
        return None
    name = collector.imports.resolve(node.func) or ""
    module, _, attr = name.rpartition(".")
    if module == "random" and attr in STDLIB_DRAWS:
        return collector.source.replace(node.func, f"self.random.{attr}")
    if module == "numpy.random" and attr in NUMPY_DRAWS:
        return collector.source.replace(node.func, f"self.rng.{attr}")
    return None


def super_call(collector: FixCollector, func: ast.FunctionDef) -> str | None:
    """The ``super().__init__(...)`` call ``func`` should make, when only one fits."""
    bases = collector.classes[-1].bases if collector.classes else []
    base = (dotted(bases[0]) or [""])[-1] if len(bases) == 1 else ""
    params = [a.arg for a in (*func.args.posonlyargs, *func.args.args)]
    params += [a.arg for a in func.args.kwonlyargs]
    if base in SUPER_ARGS and set(SUPER_ARGS[base]) <= set(params):
        return f"super().__init__({', '.join(SUPER_ARGS[base])})"
    present = [p for p in MODEL_KEYWORDS if p in params]
    if base == "Model" and len(present) <= 1:
        return f"super().__init__({', '.join(f'{p}={p}' for p in present)})"
    return None


def fix_super(collector: FixCollector, func: ast.FunctionDef) -> Edit | None:
    """MDL002: insert the base class's ``__init__`` call as the first statement."""
    call = super_call(collector, func)
    body = func.body
    has_doc = isinstance(body[0], ast.Expr) and isinstance(
        getattr(body[0], "value", None), ast.Constant
    )
    if call is None or (has_doc and len(body) == 1):
        return None
    first = body[1] if has_doc else body[0]
    source = collector.source
    line = source.line_text(first.lineno)
    indent = line.encode("utf-8")[: first.col_offset].decode("utf-8", "ignore")
    if indent.strip():
        return None  # the statement shares its line with something else
    ending = line[len(line.rstrip("\r\n")) :] or "\n"
    start = source.starts[first.lineno - 1]
    return Edit(start, start, f"{indent}{call}{ending}")


def mentions_agents(node: ast.AST) -> bool:
    """Whether a name or attribute in ``node`` says it holds agents."""
    for child in ast.walk(node):
        name = getattr(child, "id", None) or getattr(child, "attr", None) or ""
        if "agent" in name.lower():
            return True
    return False


def fix_set_loop(collector: FixCollector, node: Located) -> Edit | None:
    """MDL003: ``for x in set(s)`` -> ``for x in sorted(set(s))``, by unique_id for agents."""
    if isinstance(node, ast.For):
        node = node.iter
    elif isinstance(node, ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp):
        node = node.generators[0].iter
    if not is_set_expr(node):
        return None
    key = AGENT_KEY if mentions_agents(node) else ""
    return collector.source.replace(
        node, f"sorted({collector.source.segment(node)}{key})"
    )


def fix_registry(collector: FixCollector, node: ast.Call) -> Edit | None:
    """MDL009: ``agents.discard(a)`` -> ``a.remove()``; ``agents.clear()`` -> ``do("remove")``."""
    if not isinstance(node.func, ast.Attribute):
        return None  # MDL009 is a method call: never reached
    method, owner = node.func.attr, node.func.value
    source = collector.source
    if method == "clear" and not (node.args or node.keywords):
        return source.replace(node, f'{source.segment(owner)}.do("remove")')
    if method in {"discard", "remove"} and len(node.args) == 1 and not node.keywords:
        agent = source.segment(node.args[0])
        if not isinstance(node.args[0], SIMPLE):
            agent = f"({agent})"
        return source.replace(node, f"{agent}.remove()")
    return None  # add(): the agent registered itself when it was created


def append_argument(source: Source, call: ast.Call, text: str) -> Edit:
    """An edit that adds ``text`` as the last argument of ``call``."""
    arguments: list[ast.expr | ast.keyword] = [*call.args, *call.keywords]
    if arguments:
        last = max(arguments, key=lambda a: (a.end_lineno or 0, a.end_col_offset or 0))
        end = source.span(last)[1]
        return Edit(end, end, f", {text}")
    start, stop = source.span(call)
    close = source.text.rindex(")", start, stop)
    return Edit(close, close, text)


def fix_sampler(collector: FixCollector, node: ast.Call) -> Edit | None:
    """MDL011 in a method: seed a qmc engine (``rng=``) or ``.rvs`` (``random_state=``)."""
    if not collector.in_method():
        return None
    name = collector.imports.resolve(node.func) or ""
    if name.rpartition(".")[0] == QMC_MODULE:
        keyword = "rng"
    elif isinstance(node.func, ast.Attribute) and node.func.attr == FROZEN_DRAW:
        keyword = "random_state"
    else:
        return None  # SALib takes an integer seed: which one is the study's choice
    for given in node.keywords:
        if given.arg in SAMPLER_SEEDS:  # passed explicitly as None
            return collector.source.replace(given.value, MODEL_GENERATOR)
    return append_argument(collector.source, node, f"{keyword}={MODEL_GENERATOR}")


# Each fixer takes the node type its rule reports (a Call, a FunctionDef, a For...).
FIXERS: dict[str, Callable[[FixCollector, Any], Edit | None]] = {
    "MDL001": fix_random,
    "MDL002": fix_super,
    "MDL003": fix_set_loop,
    "MDL009": fix_registry,
    "MDL011": fix_sampler,
}
