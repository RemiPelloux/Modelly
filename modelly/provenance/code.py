"""What code a run executed: the model's source files, their hashes and the git state.

The code root is the folder of the file that defines the model class. Its source files
are the ``.py`` files under that folder that the run imported. When the folder is in a
git working tree and ``git`` is on the PATH, the commit and a hash of the uncommitted
diff are recorded too; without git the file hashes alone identify the code.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from modelly.provenance.files import hash_bytes, hash_file, hash_mapping

GIT_TIMEOUT_SECONDS = 30
POSIX = os.name == "posix"


def _resolver() -> Callable[[str], Path]:
    """``Path(name).resolve()``, resolving each folder once rather than every file's path.

    Most modules share a few folders; a file that is itself a link is resolved whole,
    and so is every file on Windows, where resolving also corrects the name's case.
    """
    folders: dict[str, str] = {}

    def resolve(name: str) -> Path:
        folder, base = os.path.split(name)
        if not POSIX or not base or os.path.islink(name):
            return Path(name).resolve()
        real = folders.get(folder)
        if real is None:
            real = folders[folder] = str(Path(folder or os.curdir).resolve())
        return Path(real, base)

    return resolve


def imported_sources(root: Path) -> list[Path]:
    """The ``.py`` files under ``root`` that an imported module was loaded from, sorted."""
    root = root.resolve()
    resolve = _resolver()
    found = set()
    for module in list(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if not name or not name.endswith(".py"):
            continue
        path = resolve(name)
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


def _read_recorded(
    root: Path, recorded: dict[str, str]
) -> tuple[list[str], dict[str, bytes]]:
    """``changed_files``, and the bytes of each unchanged file (every file read once)."""
    changed, contents = [], {}
    for name, expected in sorted(recorded.items()):
        path = root.joinpath(*name.split("/"))
        data = path.read_bytes() if path.is_file() else None
        if data is None or hash_bytes(data) != expected:
            changed.append(name)
        else:
            contents[name] = data
    return changed, contents


def changed_files(root: Path, recorded: dict[str, str]) -> list[str]:
    """The recorded files under ``root`` that are missing or whose bytes changed."""
    changed = []
    for name, expected in sorted(recorded.items()):
        path = root.joinpath(*name.split("/"))
        if not path.is_file() or hash_file(path) != expected:
            changed.append(name)
    return changed
