"""What code a run executed: the model's source files, their hashes and the git state.

The code root is the folder of the file that defines the model class. Its source files
are the ``.py`` files under that folder that the run imported. When the folder is in a
git working tree and ``git`` is on the PATH, the commit and a hash of the uncommitted
diff are recorded too; without git the file hashes alone identify the code.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from modelly.provenance.files import hash_bytes, hash_file, hash_mapping

GIT_TIMEOUT_SECONDS = 30


def imported_sources(root: Path) -> list[Path]:
    """The ``.py`` files under ``root`` that an imported module was loaded from, sorted."""
    root = root.resolve()
    found = set()
    for module in list(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if not name or not name.endswith(".py"):
            continue
        path = Path(name).resolve()
        if path.is_relative_to(root) and path.is_file():
            found.add(path)
    return sorted(found)


def file_hashes(root: Path, files: list[Path]) -> dict[str, str]:
    """``{posix path relative to root: hash}`` for each file."""
    root = root.resolve()
    return {
        path.resolve().relative_to(root).as_posix(): hash_file(path) for path in files
    }


def _git(root: Path, *args: str) -> bytes | None:
    """The stdout of ``git -C root ARGS``, or None when git is absent or fails."""
    executable = shutil.which("git")
    if executable is None:
        return None
    try:
        done = subprocess.run(
            [executable, "-C", str(root), *args],
            capture_output=True,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def git_state(root: Path) -> dict[str, Any] | None:
    """Commit, dirty flag and diff hash of the code root, or None outside a git tree."""
    commit = _git(root, "rev-parse", "HEAD")
    if commit is None:
        return None
    status = _git(root, "status", "--porcelain", "--", ".") or b""
    diff = _git(root, "diff", "HEAD", "--binary", "--", ".") or b""
    return {
        "commit": commit.decode("ascii", "replace").strip(),
        "dirty": bool(status.strip()),
        "diff_hash": hash_bytes(diff),
    }


def code_record(root: Path, root_text: str) -> dict[str, Any]:
    """The manifest's code block; ``root_text`` is the root as the manifest stores it."""
    hashes = file_hashes(root, imported_sources(root))
    return {
        "files": hashes,
        "git": git_state(root),
        "hash": hash_mapping(hashes),
        "root": root_text,
    }


def changed_files(root: Path, recorded: dict[str, str]) -> list[str]:
    """The recorded files under ``root`` that are missing or whose bytes changed."""
    changed = []
    for name, expected in sorted(recorded.items()):
        path = root.joinpath(*name.split("/"))
        if not path.is_file() or hash_file(path) != expected:
            changed.append(name)
    return changed
