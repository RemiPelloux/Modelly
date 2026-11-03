"""The 2.0 inventory matches the code's deprecations, the documentation and the roadmap."""

import ast
import re
from pathlib import Path

from modelly._inventory import CHANGES, DEPRECATIONS, pending

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "modelly"
DOCS = (ROOT / "docs" / "deprecations.md").read_text(encoding="utf-8")


def deprecated_calls():
    """``(module, first argument or None)`` of every ``deprecated()`` call in modelly/."""
    found = set()
    for path in PACKAGE.rglob("*.py"):
        if path.name == "_deprecation.py":
            continue
        module = ".".join(path.relative_to(ROOT).with_suffix("").parts)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "deprecated"
            ):
                first = node.args[0] if node.args else None
                name = first.value if isinstance(first, ast.Constant) else None
                found.add((module, name))
    return found


def table(heading):
    """The rows of the Markdown table under ``heading``, as lists of cells."""
    section = DOCS.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in row.strip("|").split(" | ")] for row in rows[2:]]


def test_every_deprecated_call_is_in_the_inventory():
    """Each call's warning names an entry, and each entry's warnings are raised."""
    calls = deprecated_calls()
    listed = {(d.module, w) for d in DEPRECATIONS for w in d.warnings}
    built = {(d.module, None) for d in DEPRECATIONS if not d.warnings}
    assert calls == listed | built


def test_the_documentation_lists_the_inventory():
    """ "Deprecated now" is the inventory's rows; "Announced for 2.0" has one row per change."""
    rows = table("Deprecated now")
    assert [(row[0], row[1]) for row in rows] == [
        (d.doc, d.replacement) for d in DEPRECATIONS
    ]
    assert all(row[2] == "2.0" for row in rows)
    assert len(table("Announced for 2.0")) == len(CHANGES)


def test_every_change_points_at_a_2_0_epic():
    """The epics exist in the 2.0 roadmap; pending and never changes say why."""
    roadmap = (ROOT / "docs" / "roadmap" / "2.0.0.md").read_text(encoding="utf-8")
    epics = set(re.findall(r"^### (H\d+) ·", roadmap, re.MULTILINE))
    assert {change.epic for change in CHANGES} <= epics
    assert all(change.warns in {"now", "pending", "never"} for change in CHANGES)
    assert all(change.reason for change in CHANGES if change.warns != "now")
    assert {change.epic for change in pending()} == {"H2", "H4", "H5"}
