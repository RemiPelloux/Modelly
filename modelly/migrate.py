"""Codemod for moving a Mesa model to Modelly.

Run as ``python -m modelly.migrate PATH [PATH ...] [--write]``. Without
``--write`` nothing is changed: the diff and the report are printed.

The rewrites are the mechanical part of ``docs/migrating_from_mesa.md``
(imports, agent constructors, a few model attributes). Everything that needs a
decision (schedulers, legacy grids, batch runs, simulators) is left in place
and reported with the guide section to read.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

GUIDE = "docs/migrating_from_mesa.md"

# Mesa module -> Modelly module. Order matters: longer prefixes first.
MODULE_MAP = (
    ("mesa.experimental.cell_space", "modelly.discrete_space"),
    ("mesa.experimental.continuous_space", "modelly.experimental.continuous_space"),
    ("mesa.experimental.meta_agents", "modelly.experimental.meta_agents"),
    ("mesa.experimental.signals", "modelly.experimental.signals"),
    ("mesa.datacollection", "modelly.datacollection"),
    ("mesa.discrete_space", "modelly.discrete_space"),
    ("mesa.visualization", "modelly.visualization"),
    ("mesa.batchrunner", "modelly.experimental.scenarios"),
    ("mesa.space", "modelly.discrete_space"),
    ("mesa.agent", "modelly.agent"),
    ("mesa.model", "modelly.model"),
    ("mesa.time", "modelly"),
    ("mesa", "modelly"),
)

# (regex, replacement) applied line by line after the import rewrite.
LINE_REWRITES = (
    (
        re.compile(
            r"super\(\)\.__init__\(\s*(?:unique_id|self\.next_id\(\)|model\.next_id\(\))\s*,\s*model\s*\)"
        ),
        "super().__init__(model)",
    ),
    (re.compile(r"\b(\w+)\.schedule\.steps\b"), r"\1.time"),
    (re.compile(r"\b(\w+)\.schedule\.agents\b"), r"\1.agents"),
    (re.compile(r"\b(\w+)\.schedule\.get_agent_count\(\)"), r"len(\1.agents)"),
    (re.compile(r"\b(\w+)\.schedule\.step\(\)"), r'\1.agents.shuffle_do("step")'),
)

# (regex, reason, guide section) for lines that need a decision.
FLAGS = (
    (
        re.compile(
            r"\b(RandomActivation(?:ByType)?|StagedActivation|SimultaneousActivation|BaseScheduler)\b"
        ),
        "scheduler class: replace with AgentSet activation",
        "activation-and-schedulers",
    ),
    (
        re.compile(r"\bself\.schedule\.(add|remove)\("),
        "schedule.add/remove: delete, agents register themselves",
        "activation-and-schedulers",
    ),
    (
        re.compile(r'shuffle_do\("step"\)'),
        "rewritten from schedule.step(): check the activation order you need",
        "activation-and-schedulers",
    ),
    (
        re.compile(r"\b(MultiGrid|SingleGrid|NetworkGrid)\("),
        "legacy grid: use the cell space",
        "grids-and-positions",
    ),
    (
        re.compile(
            r"\.(place_agent|move_agent|move_to_empty|get_neighbors|get_neighborhood|get_cell_list_contents|is_cell_empty|coord_iter|out_of_bounds)\("
        ),
        "legacy grid call: use cells",
        "grids-and-positions",
    ),
    (
        re.compile(r"\bself\.pos\b"),
        "agent.pos: use self.cell.coordinate",
        "grids-and-positions",
    ),
    (
        re.compile(r"\bPropertyLayer\("),
        "PropertyLayer: use grid.create_property_layer",
        "grids-and-positions",
    ),
    (
        re.compile(r"def __init__\(\s*self\s*,\s*unique_id\b"),
        "unique_id parameter: Modelly assigns ids, remove it here and at the callers",
        "agents",
    ),
    (re.compile(r"\.next_id\(\)"), "next_id(): delete, ids are automatic", "agents"),
    (
        re.compile(r"\bbatch_run\("),
        "batch_run: use scenarios and run_scenarios",
        "batch-runs",
    ),
    (
        re.compile(r"\b(ABMSimulator|DEVSimulator)\b"),
        "simulator: schedule on the model instead",
        "events-and-simulators",
    ),
    # Keyword form only (``seed=42``): a ``seed = ...`` assignment is the user's own variable.
    (re.compile(r"\bseed=(?!=)"), "seed=: Model and Scenario take rng=", "model"),
    (re.compile(r"\bself\.steps\b"), "self.steps: use self.time", "model"),
    (
        re.compile(r"\bModularServer\b|\bmesa\.visualization\.modules\b"),
        "Mesa 2 visualization: rewrite with SolaraViz",
        "visualization",
    ),
)

IMPORT_RE = re.compile(r"^(\s*)(from|import)\s+(mesa(?:\.[\w.]+)?)(\b.*)$")


@dataclass
class Finding:
    """One line that needs a human decision."""

    path: Path
    line: int
    text: str
    reason: str
    section: str


@dataclass
class FileResult:
    """The outcome of migrating one file."""

    path: Path
    original: str
    migrated: str
    findings: list[Finding]

    @property
    def changed(self) -> bool:
        """Whether any rewrite applied."""
        return self.migrated != self.original


def map_module(name: str) -> str:
    """Translate a dotted ``mesa...`` module name to its Modelly module."""
    for old, new in MODULE_MAP:
        if name == old or name.startswith(old + "."):
            return new + name[len(old) :]
    return name


def rewrite_line(line: str) -> str:
    """Apply the import and expression rewrites to one line."""
    match = IMPORT_RE.match(line)
    if match:
        indent, keyword, module, rest = match.groups()
        line = f"{indent}{keyword} {map_module(module)}{rest}"
    line = re.sub(r"\bmesa\.(?=\w)", "modelly.", line)
    for pattern, replacement in LINE_REWRITES:
        line = pattern.sub(replacement, line)
    return line


def find_flags(path: Path, lines: list[str]) -> list[Finding]:
    """Collect the lines that still need a decision after rewriting."""
    findings = []
    for number, text in enumerate(lines, start=1):
        for pattern, reason, section in FLAGS:
            if pattern.search(text):
                findings.append(Finding(path, number, text.strip(), reason, section))
    return findings


def migrate_source(path: Path, source: str) -> FileResult:
    """Rewrite one file's source and report what is left to do."""
    lines = [rewrite_line(line) for line in source.splitlines()]
    migrated = "\n".join(lines) + ("\n" if source.endswith("\n") else "")
    return FileResult(path, source, migrated, find_flags(path, lines))


def python_files(paths: list[Path]) -> list[Path]:
    """Expand files and directories into the Python files to migrate."""
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(
                sorted(p for p in path.rglob("*.py") if ".venv" not in p.parts)
            )
        elif path.suffix == ".py":
            files.append(path)
    return files


def render_diff(result: FileResult) -> str:
    """Unified diff of the rewrites for one file."""
    return "".join(
        difflib.unified_diff(
            result.original.splitlines(keepends=True),
            result.migrated.splitlines(keepends=True),
            fromfile=str(result.path),
            tofile=str(result.path),
        )
    )


def render_report(results: list[FileResult]) -> str:
    """The human-facing report: rewrites applied and decisions left."""
    changed = sum(result.changed for result in results)
    findings = [finding for result in results for finding in result.findings]
    out = [
        f"\nMigration report: {len(results)} file(s), {changed} rewritten, {len(findings)} line(s) to review."
    ]
    for finding in findings:
        out.append(f"  {finding.path}:{finding.line}: {finding.reason}")
        out.append(f"      {finding.text}")
        out.append(f"      see {GUIDE}#{finding.section}")
    if not findings and results:
        out.append("  Nothing left to review: run your tests with -W error.")
    return "\n".join(out)


def migrate(paths: list[Path], write: bool = False) -> list[FileResult]:
    """Migrate the Python files under ``paths``; write them back if ``write``."""
    results = []
    for path in python_files(paths):
        result = migrate_source(path, path.read_text(encoding="utf-8"))
        if write and result.changed:
            path.write_text(result.migrated, encoding="utf-8")
        results.append(result)
    return results


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        prog="python -m modelly.migrate",
        description="Rewrite the mechanical parts of a Mesa model for Modelly and report the rest.",
    )
    parser.add_argument("paths", nargs="+", type=Path, help="files or directories")
    parser.add_argument(
        "--write", action="store_true", help="apply the rewrites in place"
    )
    args = parser.parse_args(argv)

    results = migrate(args.paths, write=args.write)
    for result in results:
        if result.changed and not args.write:
            sys.stdout.write(render_diff(result))
    sys.stdout.write(render_report(results) + "\n")
    if args.write:
        sys.stdout.write(
            f"Wrote {sum(result.changed for result in results)} file(s).\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
