"""The local CI gate in Python: the stages of ``scripts/ci-local.sh``, without bash.

``python -m modelly.dev gate`` runs lint, format, types, test and audit in order, in the
Modelly checkout this package belongs to, with the current interpreter: ruff and pytest as
``python -m ruff`` and ``python -m pytest``, the size audit as ``scripts/pelloux_audit.py``.
The types stage runs mypy in strict mode on the packages ``[tool.mypy]`` in pyproject.toml
lists: ``python -m mypy`` when mypy is installed, else ``uvx`` with the pinned mypy, else it
is skipped and says so. Like the bash gate, it skips ``tests/viz`` and ``tests/examples``
when solara is not installed, and the test stage refreshes the coverage badge.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO

STAGES = ("lint", "format", "types", "test", "audit")
TYPE_CHECKER = "mypy"
TYPE_CHECKER_PIN = "mypy==2.4.0"  # run through uvx when mypy is not installed
UVX = "uvx"
NO_TYPE_CHECKER = "mypy not installed: pip install mypy or install uv"
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


def type_check_command(python: str = sys.executable) -> Command | None:
    """The mypy command (settings in pyproject.toml); None without mypy or uvx."""
    if importlib.util.find_spec(TYPE_CHECKER) is not None:
        return [python, "-m", TYPE_CHECKER]
    if shutil.which(UVX) is not None:
        return [UVX, TYPE_CHECKER_PIN, "--python-executable", python]
    return None


def skip_reason(name: str) -> str | None:
    """Why stage ``name`` cannot run on this machine, or None when it can."""
    if name == "types" and type_check_command() is None:
        return NO_TYPE_CHECKER
    return None


def stage_commands(name: str, python: str = sys.executable) -> list[Command]:
    """The commands of stage ``name``, run in order until one fails."""
    # Warnings are errors, as in the hosted build workflow (-Werror).
    warnings = ["-W", "error", "-W", "default::PendingDeprecationWarning"]
    pytest = [python, "-m", "pytest", "-q", *warnings, "-p", "pytest_cov", "--cov"]
    commands = {
        "lint": [[python, "-m", "ruff", "check", "."]],
        "format": [[python, "-m", "ruff", "format", "--check", "."]],
        "types": [command] if (command := type_check_command(python)) else [],
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
    outcomes: dict[str, str] = {}
    for name in selected:
        out.write(f"==> {name}\n")
        out.flush()
        reason = skip_reason(name)
        if reason is not None:
            outcomes[name] = "skipped"
            out.write(f"<== {name}: skipped ({reason})\n\n")
            continue
        outcomes[name] = "passed" if run_stage(name, root, runner) else "failed"
        out.write(f"<== {name}: {outcomes[name]}\n\n")
    out.write("ci-local summary\n")
    for name in selected:
        out.write(f"  {outcomes[name]}  {name}\n")
    return EXIT_FAILED if "failed" in outcomes.values() else EXIT_PASSED
