"""The rules of ``modelly.lint`` and the AST helpers they share.

Codes below 100 are errors: the model runs but gives a wrong or unreproducible result.
Codes from 100 are warnings: the model is right but its cost grows faster than it needs to.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

GUIDE = "https://remipelloux.github.io/Modelly/lint.html"

AGENT_BASES = frozenset({"Agent", "CellAgent", "FixedAgent", "ContinuousSpaceAgent"})
MODEL_BASES = frozenset({"Model"})
# Methods of an AgentSet that visit every member.
SCANS = frozenset({"select", "agg", "groupby", "sort", "map"})
# numpy.random names that build a seeded generator rather than draw from the global one.
NUMPY_SEEDED = frozenset(
    {"Generator", "PCG64", "Philox", "SFC64", "MT19937", "SeedSequence"}
)
STEP_COMPLEXITY_LIMIT = 12


@dataclass(frozen=True)
class Rule:
    """One check: its code, how serious it is, what it found and what to do instead."""

    code: str
    severity: str
    message: str
    hint: str


RULES = {
    rule.code: rule
    for rule in (
        Rule(
            "MDL001",
            "error",
            "random draw outside the model's generators",
            "use self.random (stdlib API) or self.rng (numpy Generator) so the seed reproduces the run",
        ),
        Rule(
            "MDL002",
            "error",
            "__init__ does not call super().__init__",
            "call super().__init__(...) first: without it the agent is never registered with the model",
        ),
        Rule(
            "MDL003",
            "error",
            "loop over a set: the order changes from run to run",
            "iterate an AgentSet, a list, or sorted(...) so the same seed gives the same run",
        ),
        Rule(
            "MDL004",
            "error",
            "mutable class attribute on an agent is shared by every agent",
            "create it in __init__ (self.items = [])",
        ),
        Rule(
            "MDL101",
            "warning",
            "an agent scans the whole population: O(N) per agent, O(N^2) per step",
            "look at neighbours through self.cell.neighborhood or a space query, or move the phase to the model as columns",
        ),
        Rule(
            "MDL102",
            "warning",
            "nested loops over the population: O(N^2) per step",
            "pair agents through the space (cells, pairs_within) or group them first (agents.groupby)",
        ),
        Rule(
            "MDL103",
            "warning",
            "hand-written activation loop",
            'use self.agents.shuffle_do("step") (random order) or self.agents.do("step") (fixed order)',
        ),
        Rule(
            "MDL104",
            "warning",
            "deepcopy inside step",
            "copy only the fields you need, or keep the previous state in a column",
        ),
        Rule(
            "MDL105",
            "warning",
            f"step has more than {STEP_COMPLEXITY_LIMIT} branches",
            "split it into named phases (move, interact, update) and call them in order",
        ),
    )
}


def dotted(node: ast.AST) -> list[str]:
    """Return the names along an attribute chain: ``self.model.agents`` -> self, model, agents."""
    parts: list[str] = []
    while True:
        if isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        elif isinstance(node, ast.Subscript):
            node = node.value
        elif isinstance(node, ast.Call):
            node = node.func
        else:
            break
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return parts[::-1]


def is_population(node: ast.AST, in_model: bool) -> bool:
    """Whether ``node`` is the model's whole population or one type of it, not a cell's agents."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in SCANS | {"shuffle", "to_list", "copy"}:
            return is_population(node.func.value, in_model)
        if node.func.attr == "values" and dotted(node.func.value)[-1:] == [
            "agents_by_type"
        ]:
            return True
    if isinstance(node, ast.Subscript):
        return dotted(node.value)[-1:] == ["agents_by_type"]
    chain = dotted(node)
    if not isinstance(node, ast.Attribute) or chain[-1:] != ["agents"]:
        return False
    return "model" in chain or (in_model and chain == ["self", "agents"])


def is_set_expr(node: ast.AST) -> bool:
    """Whether ``node`` builds a set, whose iteration order follows memory addresses."""
    if isinstance(node, ast.Set | ast.SetComp):
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "set"
    )


def is_mutable_literal(node: ast.AST | None) -> bool:
    """Whether ``node`` is ``[]``, ``{}``, a set literal or an empty list/dict/set call."""
    if isinstance(
        node, ast.List | ast.Dict | ast.Set | ast.ListComp | ast.DictComp | ast.SetComp
    ):
        return True
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"list", "dict", "set"}
    )


def calls_super_init(func: ast.FunctionDef) -> bool:
    """Whether ``func`` calls ``super().__init__`` or ``<Base>.__init__(self, ...)``."""
    for node in ast.walk(func):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "__init__":
            continue
        target = node.func.value
        if isinstance(target, ast.Call) and getattr(target.func, "id", None) == "super":
            return True
        if isinstance(target, ast.Name | ast.Attribute):
            return True
    return False


def branches(func: ast.FunctionDef) -> int:
    """Count the decision points of ``func``: its cyclomatic complexity minus one."""
    count = 0
    for node in ast.walk(func):
        if isinstance(
            node, ast.If | ast.For | ast.While | ast.IfExp | ast.ExceptHandler
        ):
            count += 1
        elif isinstance(node, ast.BoolOp):
            count += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            count += 1 + len(node.ifs)
    return count
