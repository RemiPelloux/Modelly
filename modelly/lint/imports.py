"""Which module each local name stands for, so a call reads as ``numpy.random.normal``."""

from __future__ import annotations

import ast


class Imports:
    """The names a module's imports bind, each mapped to the dotted name it stands for."""

    def __init__(self) -> None:
        """Start with no imports seen."""
        self.names: dict[str, str] = {}

    def add(self, node: ast.Import | ast.ImportFrom) -> None:
        """Record the names ``node`` binds; relative imports are the project's own code."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    self.names[alias.asname] = alias.name
                else:
                    root = alias.name.split(".")[0]
                    self.names[root] = root
            return
        if node.level or not node.module:
            return
        for alias in node.names:
            self.names[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def resolve(self, node: ast.AST) -> str | None:
        """Return the dotted name ``node`` stands for, or None when it is not an import."""
        parts: list[str] = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if not isinstance(node, ast.Name) or node.id not in self.names:
            return None
        return ".".join([self.names[node.id], *reversed(parts)])
