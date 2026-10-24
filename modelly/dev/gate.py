"""The local CI gate in Python: the stages of ``scripts/ci-local.sh``, without bash.

``python -m modelly.dev gate`` runs lint, format, test and audit in order, in the Modelly
checkout this package belongs to, with the current interpreter: ruff and pytest as
``python -m ruff`` and ``python -m pytest``, the size audit as ``scripts/pelloux_audit.py``.
Like the bash gate, it skips ``tests/viz`` and ``tests/examples`` when solara is not
installed, and the test stage refreshes the coverage badge.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO

STAGES = ("lint", "format", "test", "audit")
OPTIONAL_EXTRA = "solara"  # tests/viz and tests/examples need it
OPTIONAL_TESTS = ("tests/viz", "tests/examples")
BADGE = "docs/images/badges/coverage.svg"
COVERAGE_XML = "coverage.xml"
AUDIT = "scripts/pelloux_audit.py"
EXIT_PASSED = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

Command = list[str]
Runner = Callable[[Command, Path], int]


class GateError(RuntimeError):
    """The gate cannot run here: this modelly is not a source checkout."""


def checkout_root() -> Path:
    """The Modelly source checkout this package was imported from.

    Raises:
        GateError: when modelly is installed without its repository (no scripts/).
    """
    root = Path(__file__).resolve().parents[2]
    if not (root / AUDIT).is_file():
        raise GateError(
            f"{root} is not a Modelly checkout (no {AUDIT}): the gate runs on the "
            "repository, so run it from a clone with this modelly on the path"
        )
    return root


def optional_skips() -> list[str]:
    """``--ignore`` options for the test folders whose optional extra is missing."""
    if importlib.util.find_spec(OPTIONAL_EXTRA) is not None:
        return []
    return [f"--ignore={folder}" for folder in OPTIONAL_TESTS]


def stage_commands(name: str, python: str = sys.executable) -> list[Command]:
    """The commands of stage ``name``, run in order until one fails."""
    pytest = [python, "-m", "pytest", "-q", "-p", "pytest_cov", "--cov"]
    commands = {
        "lint": [[python, "-m", "ruff", "check", "."]],
        "format": [[python, "-m", "ruff", "format", "--check", "."]],
        "test": [
            [*pytest, f"--cov-report=xml:{COVERAGE_XML}", *optional_skips()],
            [python, "scripts/coverage_badge.py", COVERAGE_XML, BADGE],
        ],
        "audit": [[python, AUDIT, "audit"]],
    }
    return commands[name]


def run_command(command: Command, cwd: Path) -> int:
    """Run ``command`` in ``cwd``, its output going to this terminal; return its status."""
    return subprocess.run(command, cwd=cwd, check=False).returncode


def run_stage(name: str, root: Path, runner: Runner = run_command) -> bool:
    """Whether every command of stage ``name`` exits 0."""
    return all(runner(command, root) == 0 for command in stage_commands(name))


def unknown_stages(names: Sequence[str]) -> list[str]:
    """The names in ``names`` that are not stages."""
    return [name for name in names if name not in STAGES]


def run_gate(
    names: Sequence[str], root: Path, out: TextIO, runner: Runner = run_command
) -> int:
    """Run the stages ``names`` (all when empty), print a summary, return the exit status."""
    selected = list(names) or list(STAGES)
    failed = []
    for name in selected:
        out.write(f"==> {name}\n")
        out.flush()
        passed = run_stage(name, root, runner)
        out.write(f"<== {name}: {'passed' if passed else 'failed'}\n\n")
        if not passed:
            failed.append(name)
    out.write("ci-local summary\n")
    for name in selected:
        out.write(f"  {'failed' if name in failed else 'passed'}  {name}\n")
    return EXIT_FAILED if failed else EXIT_PASSED
