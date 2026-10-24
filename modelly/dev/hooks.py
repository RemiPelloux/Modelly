"""``python -m modelly.dev perf`` and ``install-hooks``: the pre-commit performance guard.

``install-hooks`` points git at ``.githooks``, whose ``pre-commit`` runs ``perf --staged``:
when the commit changes Modelly's code, the core operations of this checkout are timed
against the last release and the commit is refused if one is slower. ``git commit
--no-verify`` skips the hook (say why in the commit message); ``MODELLY_SKIP_PERF=1`` too.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TextIO

from modelly.dev.perf import DEFAULT_PAIRS, DEFAULT_THRESHOLD, compare, report
from modelly.dev.perf_env import (
    PerfEnvError,
    baseline_version,
    candidate_env,
    ensure_baseline,
    ensure_native,
    git,
)

HOOKS_DIR = ".githooks"
CODE_PREFIX = "modelly/"
CODE_SUFFIXES = (".py", ".c", ".h")
SKIP_ENV = "MODELLY_SKIP_PERF"
EXIT_PASSED, EXIT_FAILED, EXIT_USAGE = 0, 1, 2


def staged_code(root: Path) -> list[str]:
    """The staged files that are Modelly's code (docs, tests and benchmarks are not)."""
    names = git(
        root, "diff", "--cached", "--name-only", "--diff-filter=ACMR"
    ).splitlines()
    return [n for n in names if n.startswith(CODE_PREFIX) and n.endswith(CODE_SUFFIXES)]


def run_perf(
    root: Path,
    out: TextIO,
    *,
    staged: bool,
    against: str | None,
    pairs: int = DEFAULT_PAIRS,
    threshold: float = DEFAULT_THRESHOLD,
) -> int:
    """Time this checkout against a release; EXIT_FAILED when an operation is slower."""
    if os.environ.get(SKIP_ENV):
        out.write(f"modelly perf: skipped ({SKIP_ENV} is set)\n")
        return EXIT_PASSED
    if staged and not staged_code(root):
        return EXIT_PASSED
    try:
        version = against or baseline_version(root)
        out.write(
            f"modelly perf: core operations, this checkout against {version}...\n"
        )
        out.flush()
        release = ensure_baseline(root, version)
        ensure_native(root)
    except PerfEnvError as error:
        out.write(f"modelly perf: {error}\n")
        return EXIT_USAGE
    timings = compare(release, root, candidate_env(root), pairs, threshold)
    out.write(report(timings, version, threshold) + "\n")
    slower = any(t.slower(threshold) for t in timings)
    if slower and staged:
        out.write(
            "commit refused: make it as fast again, or commit with --no-verify and say why\n"
        )
    return EXIT_FAILED if slower else EXIT_PASSED


def install_hooks(root: Path, out: TextIO) -> int:
    """Point git at the checkout's hooks folder (``core.hooksPath``)."""
    if not (root / HOOKS_DIR / "pre-commit").is_file():
        out.write(f"modelly.dev: no {HOOKS_DIR}/pre-commit in {root}\n")
        return EXIT_USAGE
    git(root, "config", "core.hooksPath", HOOKS_DIR)
    out.write(
        f"git now runs {HOOKS_DIR}/pre-commit before every commit "
        "(the performance guard; git commit --no-verify skips it)\n"
    )
    return EXIT_PASSED


def main_perf(root: Path, args) -> int:
    """The ``perf`` command's entry point."""
    return run_perf(
        root,
        sys.stdout,
        staged=args.staged,
        against=args.against,
        pairs=args.pairs,
        threshold=args.threshold,
    )
