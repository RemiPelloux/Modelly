"""Source patterns behind the rules that look at one call or one loop at a time."""

from __future__ import annotations

import ast

from modelly.lint.rules import (
    NETWORK_CALLS,
    NETWORK_MODULES,
    NUMPY_SEEDED,
    SDK_CALL_CHAINS,
    dotted,
)

# scipy.stats.qmc engines: without rng= (or the older seed=) they scramble from global state.
QMC_MODULE = "scipy.stats.qmc"
QMC_ENGINES = frozenset(
    {"LatinHypercube", "Sobol", "Halton", "PoissonDisk"}
    | {"MultivariateNormalQMC", "MultinomialQMC"}
)
SALIB_SAMPLE = "SALib.sample."  # SALib.sample.<method>.sample(problem, n, seed=None)
FROZEN_DRAW = "rvs"  # scipy.stats distributions: rvs(..., random_state=None)
SAMPLER_SEEDS = frozenset({"rng", "seed", "random_state"})


def unseeded(call: ast.Call) -> bool:
    """Whether ``call`` passes no seed: no argument at all, or an explicit None."""
    seeds = [*call.args[:1], *(k.value for k in call.keywords if k.arg == "seed")]
    if not seeds:
        return not call.keywords
    return any(isinstance(s, ast.Constant) and s.value is None for s in seeds)


def is_global_random(name: str, call: ast.Call) -> bool:
    """MDL001: a draw from, or a generator seeded by, something other than the model.

    ``name`` is the call's resolved dotted name, e.g. ``numpy.random.normal``.
    """
    module, _, attr = name.rpartition(".")
    if module == "random":
        return attr != "Random" or unseeded(call)
    if module != "numpy.random":
        return False
    if attr == "default_rng" or (attr in NUMPY_SEEDED and attr != "Generator"):
        return unseeded(call)
    return attr != "Generator"


def passes_seed(call: ast.Call) -> bool:
    """Whether ``call`` passes ``rng=``, ``seed=`` or ``random_state=`` (not None), or ``**kw``."""
    return any(
        keyword.arg is None
        or (
            keyword.arg in SAMPLER_SEEDS
            and not (
                isinstance(keyword.value, ast.Constant) and keyword.value.value is None
            )
        )
        for keyword in call.keywords
    )


def is_unseeded_sampler(name: str, call: ast.Call) -> bool:
    """MDL011: a qmc engine, a SALib sampler or a scipy ``.rvs`` draw given no seed.

    ``name`` is the call's resolved dotted name, e.g. ``scipy.stats.qmc.Sobol``.
    """
    module, _, attr = name.rpartition(".")
    sampler = (module == QMC_MODULE and attr in QMC_ENGINES) or (
        name.startswith(SALIB_SAMPLE) and attr == "sample"
    )
    draws = isinstance(call.func, ast.Attribute) and call.func.attr == FROZEN_DRAW
    return (sampler or draws) and not passes_seed(call)


def is_network_call(name: str, func: ast.AST) -> bool:
    """MDL012: an HTTP or provider SDK call, by resolved ``name`` or by method chain."""
    if name in NETWORK_CALLS or name.split(".", maxsplit=1)[0] in NETWORK_MODULES:
        return True
    chain = tuple(dotted(func))
    return any(chain[-len(tail) :] == tail for tail in SDK_CALL_CHAINS)


def sorts_by_id(call: ast.Call) -> bool:
    """MDL006: ``key=id`` or ``key=lambda a: id(a)``, an order that follows memory addresses."""
    for keyword in call.keywords:
        key = keyword.value
        if keyword.arg != "key":
            continue
        if isinstance(key, ast.Lambda):
            key = key.body.func if isinstance(key.body, ast.Call) else key.body
        if isinstance(key, ast.Name) and key.id == "id":
            return True
    return False


def removed_in_loop(loop: ast.For) -> ast.Call | None:
    """MDL007: the first ``other.remove()`` in the body that is not the loop's own agent."""
    own = {"self", getattr(loop.target, "id", "")}
    for node in ast.walk(ast.Module(body=loop.body, type_ignores=[])):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        receiver = node.func.value
        if node.func.attr != "remove" or node.args or node.keywords:
            continue
        if not (isinstance(receiver, ast.Name) and receiver.id in own):
            return node
    return None


def declared_shared(statement: ast.stmt) -> bool:
    """MDL004 exemptions: ``__slots__``, or an annotation that says ``ClassVar``."""
    if isinstance(statement, ast.AnnAssign):
        annotation = statement.annotation
        if isinstance(annotation, ast.Subscript):
            annotation = annotation.value
        if dotted(annotation)[-1:] == ["ClassVar"]:
            return True
        targets = [statement.target]
    else:
        targets = getattr(statement, "targets", [])
    return any(isinstance(t, ast.Name) and t.id == "__slots__" for t in targets)


def column_names(tree: ast.AST) -> set[str]:
    """The attributes declared as ``name = Column(...)`` in any class of the module."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            names |= class_columns(node)
    return names


def class_columns(node: ast.ClassDef) -> set[str]:
    """The attributes declared as ``name = Column(...)`` in the body of one class."""
    names: set[str] = set()
    for statement in node.body:
        value = getattr(statement, "value", None)
        target = getattr(statement, "target", None) or next(
            iter(getattr(statement, "targets", [])), None
        )
        func = value.func if isinstance(value, ast.Call) else None
        called = getattr(func, "id", None) or getattr(func, "attr", None)
        if called == "Column" and isinstance(target, ast.Name):
            names.add(target.id)
    return names


def has_call(node: ast.AST) -> bool:
    """Whether ``node`` calls anything, which a column expression cannot always replace."""
    return any(isinstance(child, ast.Call) for child in ast.walk(node))


def writes_columns_only(loop: ast.For, columns: set[str]) -> bool:
    """MDL107: every statement of the body sets a column of the loop's agent, without calls."""
    if not (columns and isinstance(loop.target, ast.Name)) or loop.orelse:
        return False
    return all(column_write(s, loop.target.id, columns) for s in loop.body)


def column_write(statement: ast.stmt, agent: str, columns: set[str]) -> bool:
    """Whether ``statement`` is ``agent.<column> (op)= expr`` or an ``if`` made of those."""
    if isinstance(statement, ast.If):
        body = [*statement.body, *statement.orelse]
        return not has_call(statement.test) and all(
            column_write(s, agent, columns) for s in body
        )
    if isinstance(statement, ast.AugAssign):
        targets = [statement.target]
    elif isinstance(statement, ast.Assign):
        targets = statement.targets
    else:
        return False
    return not has_call(statement.value) and all(
        isinstance(t, ast.Attribute)
        and isinstance(t.value, ast.Name)
        and t.value.id == agent
        and t.attr in columns
        for t in targets
    )
