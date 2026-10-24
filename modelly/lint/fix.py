"""``modelly lint --fix`` and ``--diff``: apply the safe fixes, or show them as a diff.

Only findings that would be reported are fixed: a ``# noqa`` comment, ``select``,
``ignore`` and ``per-file-ignores`` keep a finding, and so its fix, out. Each pass
re-lints the new text, so a fix nested in another is applied on the next pass.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from modelly.lint import Finding, lint_source, python_files
from modelly.lint.edits import Source, apply_edits, unified_diff
from modelly.lint.fixers import FIXERS, FixCollector

FIX_PASSES = 4  # nested fixes need one pass per level; real code has one or two

Keep = Callable[[Finding], bool]


def fix_pass(text: str, path: str, keep: Keep) -> tuple[str, int]:
    """Apply once the fixes of the findings ``keep`` accepts; return the text and count."""
    targets = {
        (f.line, f.column, f.rule.code)
        for f in lint_source(text, path)
        if f.rule.code in FIXERS and keep(f)
    }
    if not targets:
        return text, 0
    collector = FixCollector(Source(text))
    collector.visit(ast.parse(text, filename=path))
    edits = [edit for hit, edit in collector.fixes if hit in targets]
    return apply_edits(text, edits)


def fix_source(
    text: str, path: str = "<string>", keep: Keep | None = None
) -> tuple[str, int]:
    """The source with every safe fix applied, and the number of edits made.

    Raises:
        SyntaxError: when ``text`` is not valid Python.
    """
    keep = keep or (lambda finding: True)
    total = 0
    for _ in range(FIX_PASSES):
        text, count = fix_pass(text, path, keep)
        total += count
        if not count:
            break
    return text, total


@dataclass
class FixReport:
    """What ``fix_paths`` changed: a diff per file and the number of edits."""

    diffs: list[str] = field(default_factory=list)
    edits: int = 0


def fix_paths(paths: Iterable[str | Path], keep: Keep, write: bool) -> FixReport:
    """Fix every Python file in ``paths``; write the files only when ``write``.

    Raises:
        SyntaxError: when a file is not valid Python.
    """
    report = FixReport()
    for path in python_files(paths):
        # Bytes, not read_text: the newline translation would turn CRLF into LF.
        before = path.read_bytes().decode("utf-8")
        after, count = fix_source(before, str(path), keep)
        if not count:
            continue
        report.edits += count
        report.diffs.append(unified_diff(path.as_posix(), before, after))
        if write:
            path.write_text(after, encoding="utf-8", newline="")
    return report
