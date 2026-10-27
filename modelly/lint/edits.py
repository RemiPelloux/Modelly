"""Source edits addressed by ast positions, applied without touching anything else.

An ``ast`` node gives a line and a UTF-8 byte column; ``Source`` turns those into string
offsets, so a fix replaces exactly the characters of one expression and keeps the
formatting and comments around it.
"""

from __future__ import annotations

import ast
import difflib
import re
from dataclasses import dataclass

# A physical line with its ending, as the tokenizer counts lines.
LINE = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+$")
# The nodes that have a position in the source.
Located = ast.expr | ast.stmt | ast.keyword | ast.arg


@dataclass(frozen=True, order=True)
class Edit:
    """Replace ``source[start:end]`` with ``text``; an insertion when start == end."""

    start: int
    end: int
    text: str


class Source:
    """A module's text with the offsets of its lines."""

    def __init__(self, text: str) -> None:
        """Split ``text`` into lines and record where each one starts."""
        self.text = text
        self.lines: list[str] = LINE.findall(text)
        self.starts = [0]
        for line in self.lines:
            self.starts.append(self.starts[-1] + len(line))

    def offset(self, line: int, column: int) -> int:
        """The string offset of 1-based ``line`` at UTF-8 byte ``column``."""
        text = self.lines[line - 1] if line <= len(self.lines) else ""
        prefix = text.encode("utf-8")[:column].decode("utf-8", errors="ignore")
        return self.starts[line - 1] + len(prefix)

    def span(self, node: Located) -> tuple[int, int]:
        """The start and end offsets of ``node`` (a parsed node always has both)."""
        start = self.offset(node.lineno, node.col_offset)
        end_line, end_column = node.end_lineno, node.end_col_offset
        if end_line is None or end_column is None:
            return start, start
        return start, self.offset(end_line, end_column)

    def segment(self, node: Located) -> str:
        """The exact source text of ``node``."""
        start, end = self.span(node)
        return self.text[start:end]

    def replace(self, node: Located, text: str) -> Edit:
        """An edit that replaces ``node`` with ``text``."""
        return Edit(*self.span(node), text)

    def line_text(self, line: int) -> str:
        """Line ``line`` (1-based) with its ending."""
        return self.lines[line - 1]


def apply_edits(text: str, edits: list[Edit]) -> tuple[str, int]:
    """Apply the edits that do not overlap an earlier one; return the text and how many.

    An overlapping edit is left for the next pass, which sees the new positions.
    """
    accepted: list[Edit] = []
    for edit in sorted(set(edits)):
        if accepted and edit.start < accepted[-1].end:
            continue
        accepted.append(edit)
    for edit in reversed(accepted):
        text = text[: edit.start] + edit.text + text[edit.end :]
    return text, len(accepted)


def unified_diff(path: str, before: str, after: str) -> str:
    """The change from ``before`` to ``after`` as a unified diff of ``path``."""
    lines = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(line if line.endswith("\n") else line + "\n" for line in lines)
