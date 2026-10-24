"""The Column attributes of agent classes a module imports from other files of the linted tree.

MDL107 needs to know which attributes are columns. A model often imports its agents from a
sibling module (``from .agents import Sheep``), so those files are found on disk, parsed once
per run and their classes' ``Column`` declarations recorded. Nothing is imported or executed.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

from modelly.lint.patterns import class_columns


class SiblingColumns:
    """Resolve ``from .agents import Sheep`` to the Column attributes ``Sheep`` declares.

    Relative imports are looked up from the importing file; absolute ones under each
    folder between the importing file and a lint root, so only the project's own files
    are read.
    """

    def __init__(self, roots: Iterable[str | Path]) -> None:
        """Search under ``roots``; a file root stands for the folder it is in."""
        resolved = (Path(root).resolve() for root in roots)
        self.roots = [root if root.is_dir() else root.parent for root in resolved]
        self.parsed: dict[Path, dict[str, set[str]]] = {}

    def imported(self, tree: ast.Module, path: str | Path) -> set[str]:
        """The Column attributes of every class ``tree`` imports from a sibling module."""
        here = Path(path).resolve()
        names: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            source = self.find(node, here)
            classes = self.classes(source) if source else {}
            for alias in node.names:
                names |= classes.get(alias.name, set())
        return names

    def find(self, node: ast.ImportFrom, here: Path) -> Path | None:
        """The file ``node`` imports from, when it is one of the project's own."""
        parts = node.module.split(".") if node.module else []
        if node.level:
            parents = here.parents
            bases = [parents[node.level - 1]] if node.level <= len(parents) else []
        else:
            bases = [folder for folder in here.parents if self.within(folder)]
        for base in bases:
            module = [base.joinpath(*parts[:-1], f"{parts[-1]}.py")] if parts else []
            for candidate in [*module, base.joinpath(*parts, "__init__.py")]:
                if candidate.is_file() and candidate != here:
                    return candidate
        return None

    def within(self, folder: Path) -> bool:
        """Whether ``folder`` is a lint root or inside one."""
        return any(folder.is_relative_to(root) for root in self.roots)

    def classes(self, source: Path) -> dict[str, set[str]]:
        """Each top-level class of ``source`` mapped to its Column attributes, parsed once.

        A class also has the columns of the bases defined before it in the same file.
        """
        if source in self.parsed:
            return self.parsed[source]
        try:
            body = ast.parse(source.read_text(encoding="utf-8"), str(source)).body
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
            body = []  # an unreadable sibling adds no columns; linting it reports it
        found: dict[str, set[str]] = {}
        for node in body:
            if isinstance(node, ast.ClassDef):
                bases = [getattr(base, "id", "") for base in node.bases]
                inherited = [found.get(base, set()) for base in bases]
                found[node.name] = class_columns(node).union(*inherited)
        self.parsed[source] = found
        return found
