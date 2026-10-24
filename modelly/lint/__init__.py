"""Static checks for Modelly models: bugs that break reproducibility and loops that scale badly.

Run as ``python -m modelly.lint PATH [PATH ...]``. Nothing is imported or executed: the source
is parsed and walked. A finding on a line ending in ``# noqa`` (or ``# noqa: MDL101``) is
skipped, and ``[tool.modelly.lint]`` in pyproject.toml selects and ignores rules (see
``modelly.lint.config``). The rules, with examples, are in ``docs/lint.md``; ``--explain
CODE`` prints one of them.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from modelly.lint.checker import Checker
from modelly.lint.rules import GUIDE, RULES, Rule
from modelly.lint.siblings import SiblingColumns

__all__ = ["GUIDE", "RULES", "Finding", "Rule", "lint_paths", "lint_source"]

# A noqa comment, bare or followed by `: CODE[, CODE ...]`; text after the codes is free.
CODE = r"[A-Z]+[0-9]+"
NOQA = re.compile(
    rf"#\s*noqa\b(?::\s*(?P<codes>{CODE}(?:[,\s]+{CODE})*))?", re.IGNORECASE
)


@dataclass(frozen=True)
class Finding:
    """One rule hit at a place in a file."""

    path: str
    line: int
    column: int
    rule: Rule

    def location(self) -> str:
        """``path:line:col: CODE message``, the format editors jump to."""
        return f"{self.path}:{self.line}:{self.column}: {self.rule.code} {self.rule.message}"

    def __str__(self) -> str:
        """The location line, then the hint."""
        return f"{self.location()}\n    hint: {self.rule.hint}"


def suppressed(line: str, code: str) -> bool:
    """Whether a ``# noqa`` comment on ``line`` covers ``code``."""
    match = NOQA.search(line)
    if not match:
        return False
    codes = match.group("codes")
    return codes is None or code in re.findall(CODE, codes.upper())


def lint_source(
    source: str, path: str = "<string>", siblings: SiblingColumns | None = None
) -> list[Finding]:
    """Return the findings for one module's source, sorted by position.

    ``siblings`` resolves the agent classes the module imports from other files of the
    project, so MDL107 knows their Column attributes; without it only this source counts.

    Raises:
        SyntaxError: when ``source`` is not valid Python.
    """
    tree = ast.parse(source, filename=path)
    imported = siblings.imported(tree, path) if siblings else set()
    checker = Checker(frozenset(imported))
    checker.visit(tree)
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
    paths = list(paths)
    siblings = SiblingColumns(paths)  # one parse per imported file for the whole run
    findings: list[Finding] = []
    for path in python_files(paths):
        source = path.read_text(encoding="utf-8")
        findings.extend(lint_source(source, str(path), siblings))
    return findings
