"""``modelly migrate --check-2.0``: what a project must change before Modelly 2.0.

Every deprecation of the 2.0 inventory (``modelly/_inventory.py``) that code can show is
looked for in the project's Python files, by reading them (nothing is imported or run):

* calls of the renamed visualisation helpers, and the ``SpaceRenderer`` calls that pass
  arguments to ``render``, ``draw_agents``, ``draw_structure`` or ``draw_property_layer``;
* an ``agent_portrayal`` that returns a dict, a ``property_layer_portrayal`` given as a dict;
* the synthetic-population names imported from ``modelly.space.geo``;
* a ``Scenario`` subclass attribute without an annotation.

Each is a **change**, with the line and what to write instead. The 2.0 changes no warning can
show are **notes**: a ``Model`` subclass without ``agent_streams = True`` draws other numbers
in 2.0 (per-agent streams by default, epic H6), and a ``requires-python`` below 3.13 must be
raised (H9). The exit status is 1 when there is a change to make, so the check fits a test or
a pre-commit hook.
"""

from __future__ import annotations

import ast
import re
import tomllib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

RENAMED = {"make_space_altair": "make_altair_space()",
           "make_space_matplotlib": "make_mpl_space_component()",
           "make_plot_measure": "make_mpl_plot_component()"}  # fmt: skip
WITH_ARGUMENTS = {"render": "setup_structure(), setup_agents(), setup_property_layer(), then render()",
                  "draw_agents": "setup_agents(...), then draw_agents()",
                  "draw_structure": "setup_structure(...), then draw_structure()",
                  "draw_property_layer": "setup_property_layer(...), then draw_property_layer()"}  # fmt: skip
MOVED = {"ipf": "modelly.population", "synthesize_population": "modelly.population",
         "MAX_ITERATIONS": "modelly.population.fitting", "REGION": "modelly.population.fitting",
         "TOLERANCE": "modelly.population.fitting"}  # fmt: skip
GEO = ("modelly.space.geo", "modelly.space.geo.population")
CHANGE, NOTE = "change", "note"


@dataclass(frozen=True)
class Finding:
    """One thing to change, or to know, before 2.0."""

    kind: str
    path: Path
    line: int
    message: str

    def __str__(self) -> str:
        """``path:line: change: message``."""
        return f"{self.path}:{self.line}: {self.kind}: {self.message}"


def _name(node: ast.AST) -> str | None:
    """The called name of a call: ``f`` of ``f(...)`` and of ``x.f(...)``."""
    func = getattr(node, "func", None)
    return getattr(func, "id", None) or getattr(func, "attr", None)


def _calls(tree: ast.AST, path: Path) -> Iterator[Finding]:
    """Renamed helpers, and renderer calls that still pass arguments."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _name(node)
        if name in RENAMED:
            yield Finding(
                CHANGE,
                path,
                node.lineno,
                f"{name}() is removed in 2.0: use {RENAMED[name]}",
            )
        elif name in WITH_ARGUMENTS and (node.args or node.keywords):
            yield Finding(
                CHANGE,
                path,
                node.lineno,
                f"{name}(...) with arguments is removed in 2.0: use {WITH_ARGUMENTS[name]}",
            )
        for keyword in node.keywords:
            if keyword.arg == "property_layer_portrayal" and isinstance(
                keyword.value, ast.Dict
            ):
                yield Finding(CHANGE, path, node.lineno, "a property_layer_portrayal dict is removed in 2.0: pass a callable returning a PropertyLayerStyle")  # fmt: skip


def _portrayals(tree: ast.AST, path: Path) -> Iterator[Finding]:
    """An ``agent_portrayal`` function that returns a dict."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "agent_portrayal":
            returns = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
            if any(isinstance(r.value, ast.Dict) for r in returns):
                yield Finding(CHANGE, path, node.lineno, "agent_portrayal returning a dict is removed in 2.0: return an AgentPortrayalStyle")  # fmt: skip


def _imports(tree: ast.AST, path: Path) -> Iterator[Finding]:
    """Population names taken from the geographic space."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in GEO:
            for alias in node.names:
                if alias.name in MOVED:
                    yield Finding(CHANGE, path, node.lineno, f"{node.module}.{alias.name} moves in 2.0: import it from {MOVED[alias.name]}")  # fmt: skip


def _bases(node: ast.ClassDef) -> set[str]:
    """The base class names of a class statement."""
    return {getattr(b, "id", None) or getattr(b, "attr", "") for b in node.bases}


def _classes(tree: ast.AST, path: Path) -> Iterator[Finding]:
    """Scenario fields without annotations; models without per-agent streams."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        assigned = [s for s in node.body if isinstance(s, ast.Assign)]
        names = {
            t.id: s for s in assigned for t in s.targets if isinstance(t, ast.Name)
        }
        if "Scenario" in _bases(node):
            for name, statement in names.items():
                if not name.startswith("_"):
                    yield Finding(CHANGE, path, statement.lineno, f"{node.name}.{name} has no annotation: 2.0 typed scenarios take only annotated fields ({name}: type = value)")  # fmt: skip
        if "Model" in _bases(node) and "agent_streams" not in names:
            yield Finding(NOTE, path, node.lineno, f"{node.name} does not set agent_streams = True: its agents draw other numbers in 2.0, where per-agent streams are the default (set it now to get 2.0's numbers)")  # fmt: skip


def check_file(path: Path) -> list[Finding]:
    """Every finding of one Python file; a file that does not parse is reported as a note."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as error:
        return [
            Finding(
                NOTE, path, getattr(error, "lineno", 0) or 0, f"not checked: {error}"
            )
        ]
    found = [
        *_calls(tree, path),
        *_portrayals(tree, path),
        *_imports(tree, path),
        *_classes(tree, path),
    ]
    return sorted(found, key=lambda f: f.line)


def _python_floor(project: Path) -> Iterator[Finding]:
    """A ``requires-python`` that still allows Python 3.12."""
    pyproject = project / "pyproject.toml"
    if not pyproject.is_file():
        return
    spec = (
        tomllib.loads(pyproject.read_text(encoding="utf-8"))
        .get("project", {})
        .get("requires-python", "")
    )
    floor = re.search(r">=\s*3\.(\d+)", spec)
    if floor and int(floor.group(1)) < 13:
        yield Finding(
            NOTE,
            pyproject,
            1,
            f"requires-python {spec!r}: Modelly 2.0 needs Python 3.13 or later",
        )


def python_files(paths: Iterable[Path]) -> list[Path]:
    """The ``.py`` files of ``paths`` (files and folders), sorted."""
    found: set[Path] = set()
    for path in paths:
        found |= {path} if path.is_file() else set(path.rglob("*.py"))
    return sorted(p for p in found if p.suffix == ".py")


def check(paths: Iterable[Path]) -> list[Finding]:
    """The findings of every Python file under ``paths``, and of their projects' metadata."""
    paths = list(paths)
    found = [f for file in python_files(paths) for f in check_file(file)]
    for folder in {p if p.is_dir() else p.parent for p in paths}:
        found += list(_python_floor(folder))
    return found


def report(findings: list[Finding]) -> str:
    """The findings, changes first, then a summary line."""
    changes = [f for f in findings if f.kind == CHANGE]
    notes = [f for f in findings if f.kind == NOTE]
    lines = [str(f) for f in changes + notes]
    lines.append(
        f"{len(changes)} change(s) to make before Modelly 2.0, {len(notes)} note(s)"
    )
    return "\n".join(lines)
