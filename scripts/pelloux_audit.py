#!/usr/bin/env python3
"""Pelloux size engine for the Modelly repo.

Two subcommands:

    python3 scripts/pelloux_audit.py audit   # ratchet against pelloux-baseline.json
    python3 scripts/pelloux_audit.py seed    # write pelloux-baseline.json from the tree

Called through scripts/audit-pelloux.sh and scripts/seed-pelloux-baseline.sh so
the command names match the other Pelloux repos.

Scope: every ``*.py`` under ``modelly/`` except ``modelly/examples/``. Limits are
documented in pelloux-guidelines.md §5 (size) and §6 (debug leftovers).
"""

from __future__ import annotations

import ast
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = ROOT / "modelly"
BASELINE_PATH = ROOT / "pelloux-baseline.json"

# Repo-relative prefixes. Examples are documentation-grade and fully exempt;
# the visualization package legitimately prints to the console.
EXEMPT_PREFIXES = ("modelly/examples/",)
CONSOLE_PREFIXES = ("modelly/visualization/",)

GENERAL_TARGET = 300
GENERAL_WARN = 330  # target + 10 %
GENERAL_HARD = 400
GENERAL_ERROR = 440  # hard limit + 10 %
FUNCTION_LIMIT = 25  # body lines, docstring excluded
DEBUG_CALLS = frozenset({"print", "breakpoint"})

WARN_REPORT = 15
LONG_FUNCTION_REPORT = 15
WORST_REPORT = 10

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass
class Report:
    """Accumulated findings for one audit run."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    long_functions: list[tuple[int, str]] = field(default_factory=list)
    worst: list[tuple[int, str]] = field(default_factory=list)

    @property
    def warning_count(self) -> int:
        """Size, console-print and long-function warnings together."""
        return len(self.warnings) + len(self.long_functions)


def iter_files() -> Iterator[tuple[str, Path]]:
    """Yield (repo-relative path, absolute path) for every scoped module."""
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(EXEMPT_PREFIXES):
            continue
        yield rel, path


def count_lines(path: Path) -> int:
    """Return the number of physical lines in ``path``."""
    with path.open(encoding="utf-8", errors="ignore") as handle:
        return sum(1 for _ in handle)


def load_baseline() -> dict[str, int]:
    """Return the per-file line ceilings recorded in pelloux-baseline.json."""
    if not BASELINE_PATH.exists():
        print(
            "Missing pelloux-baseline.json — run: bash scripts/seed-pelloux-baseline.sh"
        )
        sys.exit(1)
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {entry["path"]: entry["lines"] for entry in data.get("oversized_files", [])}


def check_size(rel: str, lines: int, ceilings: dict[str, int], report: Report) -> None:
    """Apply the file-size limits, or the baseline ratchet for grandfathered files."""
    ceiling = ceilings.get(rel)
    if ceiling is not None:
        if lines > ceiling:
            report.errors.append(
                f"{rel} grew: {ceiling} -> {lines} lines (baseline ratchet)"
            )
        report.worst.append((lines, rel))
        return
    if lines > GENERAL_ERROR:
        report.errors.append(
            f"{rel} — {lines} lines (hard limit {GENERAL_ERROR} = {GENERAL_HARD}+10 %, "
            f"target {GENERAL_TARGET}, not in baseline)"
        )
    elif lines > GENERAL_WARN:
        report.warnings.append(f"{rel} — {lines} lines (target {GENERAL_TARGET})")
    if lines > GENERAL_TARGET:
        report.worst.append((lines, rel))


def parse_module(rel: str, path: Path, report: Report) -> ast.Module | None:
    """Parse ``path``; a syntax error is reported as an ERROR and yields ``None``."""
    try:
        return ast.parse(
            path.read_text(encoding="utf-8", errors="ignore"), filename=rel
        )
    except SyntaxError as exc:
        report.errors.append(f"{rel}:{exc.lineno} — cannot parse: {exc.msg}")
        return None


def debug_calls(tree: ast.Module) -> list[tuple[int, str]]:
    """Return (line, name) for every ``print(...)`` or ``breakpoint()`` call."""
    return sorted(
        (node.lineno, node.func.id)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in DEBUG_CALLS
    )


def check_debug_leftovers(rel: str, tree: ast.Module, report: Report) -> None:
    """Flag debug calls: ERROR in general code, WARN under the console packages."""
    console = rel.startswith(CONSOLE_PREFIXES)
    bucket = report.warnings if console else report.errors
    label = "console output" if console else "debug leftover"
    for lineno, name in debug_calls(tree):
        bucket.append(f"{rel}:{lineno} — {name}() call ({label})")


def body_length(node: FunctionNode) -> int:
    """Return the source lines spanned by a function body, docstring excluded."""
    body = node.body
    if ast.get_docstring(node, clean=False) is not None:
        body = body[1:]
    if not body or body[-1].end_lineno is None:
        return 0
    return body[-1].end_lineno - body[0].lineno + 1


def check_long_functions(rel: str, tree: ast.Module, report: Report) -> None:
    """Record every function or method whose body exceeds FUNCTION_LIMIT lines."""
    for node in ast.walk(tree):
        if not isinstance(node, FunctionNode):
            continue
        length = body_length(node)
        if length > FUNCTION_LIMIT:
            report.long_functions.append((length, f"{rel}:{node.lineno} {node.name}()"))


def print_warnings(report: Report) -> None:
    """Print the WARN lines: size/console warnings, then the worst long functions."""
    for message in report.warnings[:WARN_REPORT]:
        print(f"  WARN: {message}")
    if len(report.warnings) > WARN_REPORT:
        print(f"  WARN: ... and {len(report.warnings) - WARN_REPORT} more")
    ranked = sorted(report.long_functions, reverse=True)
    for length, where in ranked[:LONG_FUNCTION_REPORT]:
        print(f"  WARN: {where} — {length}-line body (limit {FUNCTION_LIMIT})")
    if len(ranked) > LONG_FUNCTION_REPORT:
        print(
            f"  WARN: ... and {len(ranked) - LONG_FUNCTION_REPORT} more long functions"
        )


def print_report(report: Report, debt: int) -> None:
    """Print WARN/ERROR lines, the summary line and the worst offenders."""
    print_warnings(report)
    for message in report.errors:
        print(f"  ERROR: {message}")
    print(
        f"\nPelloux audit — {len(report.errors)} error(s), {report.warning_count} warning(s), "
        f"{debt} grandfathered oversized file(s)."
    )
    if report.worst:
        print("\n  Worst offenders (refactor candidates):")
        for lines, rel in sorted(report.worst, reverse=True)[:WORST_REPORT]:
            print(f"    {lines:>5} lines  {rel}")


def audit() -> int:
    """Run every check against the tree; return the process exit code."""
    ceilings = load_baseline()
    report = Report()
    for rel, path in iter_files():
        check_size(rel, count_lines(path), ceilings, report)
        tree = parse_module(rel, path, report)
        if tree is None:
            continue
        check_debug_leftovers(rel, tree, report)
        check_long_functions(rel, tree, report)
    print_report(report, len(ceilings))
    if report.errors:
        print(
            "\nPelloux audit failed. Fix the errors above or re-seed the baseline deliberately."
        )
        return 1
    return 0


def seed() -> int:
    """Write pelloux-baseline.json from every scoped file above the hard limit."""
    files = [
        {"path": rel, "lines": lines}
        for rel, path in iter_files()
        if (lines := count_lines(path)) > GENERAL_ERROR
    ]
    payload = json.dumps({"oversized_files": files}, indent=2) + "\n"
    BASELINE_PATH.write_text(payload, encoding="utf-8")
    print(
        f"Wrote {BASELINE_PATH.relative_to(ROOT)} — {len(files)} file(s) > {GENERAL_ERROR}."
    )
    return 0


def main(argv: list[str]) -> int:
    """Dispatch ``audit`` (default) or ``seed``."""
    command = argv[1] if len(argv) > 1 else "audit"
    if command == "seed":
        return seed()
    if command == "audit":
        return audit()
    print(f"Unknown command {command!r}; expected 'audit' or 'seed'.")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
