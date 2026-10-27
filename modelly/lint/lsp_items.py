"""The LSP shapes of the linter's results: Diagnostic, TextEdit and CodeAction.

A finding's column is a UTF-8 byte offset (``ast``) and a fix's edit a string offset
(``modelly.lint.edits``); LSP positions count UTF-16 code units. A diagnostic carries the
finding's own line and column in ``data``, so a code action finds the fix for it exactly.
"""

from __future__ import annotations

from typing import Any

from modelly.lint import Finding
from modelly.lint.edits import Edit, Source
from modelly.lint.rpc import offset_position, utf16_column
from modelly.lint.rules import GUIDE

__all__ = ["action", "diagnostic", "hit_of", "text_edit"]

SOURCE = "modelly"
SEVERITY = {"error": 1, "warning": 2}  # LSP DiagnosticSeverity
QUICKFIX = "quickfix"

Params = dict[str, Any]


def diagnostic(finding: Finding, lines: list[str]) -> Params:
    """One finding as an LSP Diagnostic, from its column to the end of its line."""
    line = lines[finding.line - 1] if finding.line <= len(lines) else ""
    start = len(line.encode()[: finding.column - 1].decode(errors="ignore"))
    rule = finding.rule
    return {
        "range": {
            "start": {"line": finding.line - 1, "character": utf16_column(line, start)},
            "end": {
                "line": finding.line - 1,
                "character": utf16_column(line, len(line)),
            },
        },
        "severity": SEVERITY[rule.severity],
        "code": rule.code,
        "codeDescription": {"href": f"{GUIDE}#{rule.code.lower()}"},
        "source": SOURCE,
        "message": f"{rule.message}\nhint: {rule.hint}",
        "data": {"line": finding.line, "column": finding.column},
    }


def text_edit(source: Source, edit: Edit) -> Params:
    """A string-offset edit as an LSP TextEdit."""
    lines = [line.rstrip("\r\n") for line in source.lines]
    return {
        "range": {
            "start": offset_position(source.starts, lines, edit.start),
            "end": offset_position(source.starts, lines, edit.end),
        },
        "newText": edit.text,
    }


def action(title: str, uri: str, diag: Params, edits: list[Params]) -> Params:
    """A quick-fix CodeAction that applies ``edits`` to ``uri``."""
    return {
        "title": title,
        "kind": QUICKFIX,
        "diagnostics": [diag],
        "edit": {"changes": {uri: edits}},
    }


def hit_of(diag: Params) -> tuple[int, int, str] | None:
    """The (line, column, code) of a diagnostic this server published, else None."""
    data, code = diag.get("data"), diag.get("code")
    if diag.get("source") != SOURCE or not isinstance(data, dict) or not code:
        return None
    line, column = data.get("line"), data.get("column")
    if not (isinstance(line, int) and isinstance(column, int)):
        return None
    return line, column, code
