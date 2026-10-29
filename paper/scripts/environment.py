"""The provenance every data file written by a paper script records.

    from environment import environment
    out = {"environment": environment(), ...}

Commit and date of the run, the interpreter, the platform, and the versions of the
packages the computation went through, so that a number in the paper can be traced to
the code and the libraries that produced it.
"""

from __future__ import annotations

import datetime as dt
import importlib.metadata as metadata
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ("modelly-abm", "numpy", "scipy", "pandas", "networkx")
GIT = shutil.which("git") or "git"


def commit() -> str:
    """The repository's HEAD commit, with ``+dirty`` when the tree has local changes."""
    head = subprocess.run(
        [GIT, "-C", str(ROOT), "rev-parse", "--short=10", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    # The data files these scripts write do not count: regenerating one must not mark
    # the next one's record dirty.
    dirty = subprocess.run(
        [
            GIT,
            "-C",
            str(ROOT),
            "status",
            "--porcelain",
            "--untracked-files=no",
            "--",
            ".",
            ":(exclude)paper/data",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return f"{head}+dirty" if dirty else head


def versions() -> dict[str, str]:
    """Installed versions of the packages the paper scripts depend on."""
    found = {}
    for name in PACKAGES:
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            found[name] = "absent"
    return found


def environment() -> dict[str, object]:
    """Commit, date, interpreter, platform and package versions of this run."""
    return {
        "commit": commit(),
        "date": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "versions": versions(),
    }
