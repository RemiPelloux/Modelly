"""Static checks for Modelly models: bugs that break reproducibility and loops that scale badly.

Run as ``python -m modelly.lint PATH [PATH ...]``. Nothing is imported or executed: the source
is parsed and walked. A finding on a line ending in ``# noqa`` (or ``# noqa: MDL101``) is
skipped. The rules, with examples, are in ``docs/lint.md``.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from modelly.lint.checker import Checker
from modelly.lint.rules import GUIDE, RULES, Rule

__all__ = ["GUIDE", "RULES", "Finding", "Rule", "lint_paths", "lint_source"]

NOQA = re.compile(r"#\s*noqa\b(?::\s*(?P<codes>[A-Z0-9,\s]+))?", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    """One rule hit at a place in a file."""

    path: str
    line: int
    column: int
    rule: Rule

    def __str__(self) -> str:
        """``path:line:col: CODE message`` then the hint, the format editors jump to."""
        head = f"{self.path}:{self.line}:{self.column}: {self.rule.code} {self.rule.message}"
        return f"{head}\n    hint: {self.rule.hint}"


def suppressed(line: str, code: str) -> bool:
    """Whether a ``# noqa`` comment on ``line`` covers ``code``."""
    match = NOQA.search(line)
    if not match:
        return False
    codes = match.group("codes")
    return codes is None or code in {c.strip().upper() for c in codes.split(",")}


def lint_source(source: str, path: str = "<string>") -> list[Finding]:
    """Return the findings for one module's source, sorted by position.

    Raises:
        SyntaxError: when ``source`` is not valid Python.
    """
    checker = Checker()
    checker.visit(ast.parse(source, filename=path))
    lines = source.splitlines()
    return [
        Finding(path, line, column, RULES[code])
        for line, column, code in sorted(checker.hits)
        if not suppressed(lines[line - 1] if line <= len(lines) else "", code)
    ]


def python_files(paths: Iterable[str | Path]) -> Iterator[Path]:
    """Yield ``paths`` that are files, and the ``.py`` files under those that are directories."""
    for path in map(Path, paths):
        if path.is_dir():
            yield from sorted(p for p in path.rglob("*.py") if ".venv" not in p.parts)
        else:
            yield path


def lint_paths(paths: Iterable[str | Path]) -> list[Finding]:
    """Return the findings for every Python file in ``paths``.

    Raises:
        SyntaxError: when a file is not valid Python.
    """
    findings: list[Finding] = []
    for path in python_files(paths):
        findings.extend(lint_source(path.read_text(encoding="utf-8"), str(path)))
    return findings
