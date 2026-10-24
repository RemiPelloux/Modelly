#!/usr/bin/env python3
"""Cut a Modelly release: check, gate, bump, commit and tag. Python, any OS.

    python scripts/release.py 1.3.0              dry run: print what would change
    python scripts/release.py 1.3.0 --apply      do it: commit chore(release) and tag v1.3.0
    python scripts/release.py 1.3.0 --apply --push
                                                 then push main and the tag

Steps, in order; the first that fails stops the release:

1. the work tree is clean and on ``main``;
2. ``python -m modelly.dev gate`` passes (``--no-gate`` skips it, for a rehearsal);
3. the version in ``modelly/__init__.py`` and ``CITATION.cff`` becomes X.Y.Z, and the
   CITATION date the release date (today, or ``--date``);
4. the CHANGELOG gets the heading ``## X.Y.Z - DATE``: an ``## Unreleased`` heading is
   renamed, otherwise the heading is inserted above the latest release;
5. one commit ``chore(release): X.Y.Z`` of exactly those three files, with no trailers;
6. the annotated tag ``vX.Y.Z``; with ``--push``, ``main`` and the tag are pushed.

The release workflow builds the wheels and the docs from the pushed tag.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git") or "git"  # full path where found (Windows: git.exe)
BRANCH = "main"
REMOTE = "origin"
INIT = Path("modelly") / "__init__.py"
CITATION = Path("CITATION.cff")
CHANGELOG = Path("CHANGELOG.md")
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
INIT_LINE = re.compile(r'^__version__ = "[^"]*"$', re.MULTILINE)
CFF_VERSION = re.compile(r'^version: "[^"]*"$', re.MULTILINE)
CFF_DATE = re.compile(r'^date-released: "[^"]*"$', re.MULTILINE)
UNRELEASED = re.compile(r"^## Unreleased[^\n]*$", re.MULTILINE)
RELEASE_HEADING = re.compile(r"^## \d", re.MULTILINE)
EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2
ENCODING = "utf-8"


class ReleaseError(RuntimeError):
    """A release step failed; the message says which and why."""


@dataclass(frozen=True)
class Release:
    """What to release, where, and how far to go."""

    version: str
    date: str
    root: Path = ROOT
    apply: bool = False
    push: bool = False
    gate: bool = True


def git(release: Release, *args: str) -> str:
    """Run git in the release's checkout and return its output; ReleaseError on failure."""
    done = subprocess.run(
        [GIT, *args],
        cwd=release.root,
        capture_output=True,
        text=True,
        encoding=ENCODING,
        check=False,
    )
    if done.returncode:
        raise ReleaseError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout.strip()


def check_tree(release: Release) -> None:
    """The tree is clean, on main, and the tag does not exist yet."""
    if git(release, "status", "--porcelain"):
        raise ReleaseError("the work tree has uncommitted changes")
    branch = git(release, "rev-parse", "--abbrev-ref", "HEAD")
    if branch != BRANCH:
        raise ReleaseError(f"releases are cut from {BRANCH}, not {branch}")
    if git(release, "tag", "--list", f"v{release.version}"):
        raise ReleaseError(f"tag v{release.version} already exists")


def run_gate(release: Release) -> None:
    """``python -m modelly.dev gate`` in the checkout must pass."""
    done = subprocess.run(
        [sys.executable, "-m", "modelly.dev", "gate"], cwd=release.root, check=False
    )
    if done.returncode:
        raise ReleaseError("the gate failed (python -m modelly.dev gate)")


def _replace(pattern: re.Pattern, text: str, line: str, what: str) -> str:
    new, count = pattern.subn(line, text, count=1)
    if not count:
        raise ReleaseError(f"no {what} line to update")
    return new


def bumped_init(text: str, version: str) -> str:
    """``modelly/__init__.py`` with ``__version__`` set to ``version``."""
    return _replace(INIT_LINE, text, f'__version__ = "{version}"', "__version__")


def bumped_citation(text: str, version: str, date: str) -> str:
    """``CITATION.cff`` with the software version and release date set."""
    text = _replace(CFF_VERSION, text, f'version: "{version}"', "CITATION version")
    return _replace(CFF_DATE, text, f'date-released: "{date}"', "CITATION date")


def bumped_changelog(text: str, version: str, date: str) -> str:
    """The changelog with the release heading: Unreleased renamed, or one inserted."""
    heading = f"## {version} - {date}"
    if re.search(rf"^## {re.escape(version)}\b", text, re.MULTILINE):
        raise ReleaseError(f"the changelog already has a {version} heading")
    if UNRELEASED.search(text):
        return UNRELEASED.sub(heading, text, count=1)
    latest = RELEASE_HEADING.search(text)
    if latest is None:
        raise ReleaseError("the changelog has no release heading to insert above")
    return f"{text[: latest.start()]}{heading}\n\n{text[latest.start() :]}"


def planned_files(release: Release) -> dict[Path, str]:
    """The new contents of every file the release changes, by relative path."""

    def read(path: Path) -> str:
        return (release.root / path).read_text(encoding=ENCODING)

    return {
        INIT: bumped_init(read(INIT), release.version),
        CITATION: bumped_citation(read(CITATION), release.version, release.date),
        CHANGELOG: bumped_changelog(read(CHANGELOG), release.version, release.date),
    }


def _commit(release: Release, message: str) -> None:
    """Commit with exactly ``message``: no hook may add a trailer to it."""
    git(release, "commit", "--no-verify", "-m", message)
    if git(release, "log", "-1", "--format=%B") != message:
        git(release, "reset", "--soft", "HEAD~1")
        raise ReleaseError("a hook changed the release commit message; commit undone")


def commit_and_tag(release: Release, files: dict[Path, str]) -> None:
    """Write the files, commit exactly them, tag, and push when asked."""
    for path, text in files.items():
        (release.root / path).write_text(text, encoding=ENCODING, newline="\n")
    git(release, "add", "--", *(path.as_posix() for path in files))
    _commit(release, f"chore(release): {release.version}")
    tag = f"v{release.version}"
    git(release, "tag", "-a", tag, "-m", f"Modelly {release.version}")
    if release.push:
        git(release, "push", REMOTE, BRANCH, tag)


def cut(release: Release, out: TextIO | None = None) -> None:
    """Run every step; a dry run stops after printing what would change."""
    out = out or sys.stdout
    check_tree(release)
    if release.gate:
        run_gate(release)
    files = planned_files(release)
    for path in files:
        out.write(
            f"{'update' if release.apply else 'would update'} {path.as_posix()}\n"
        )
    tag = f"v{release.version}"
    if not release.apply:
        out.write(f"would commit chore(release): {release.version} and tag {tag}\n")
        out.write("dry run: nothing changed (pass --apply)\n")
        return
    commit_and_tag(release, files)
    out.write(f"committed and tagged {tag}{' and pushed' if release.push else ''}\n")


def build_parser() -> argparse.ArgumentParser:
    """The command line: the version and how far to go."""
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog="Without --apply nothing is written. --push needs --apply.",
    )
    parser.add_argument("version", help="the version to release, X.Y.Z")
    parser.add_argument("--apply", action="store_true", help="commit and tag")
    parser.add_argument("--push", action="store_true", help="push main and the tag")
    parser.add_argument("--no-gate", action="store_true", help="skip the gate")
    parser.add_argument("--date", help="release date, YYYY-MM-DD (default: today)")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse, validate and cut the release; the exit status says how it went."""
    args = build_parser().parse_args(argv)
    if not VERSION.match(args.version) or (args.push and not args.apply):
        sys.stderr.write("release: the version is X.Y.Z, and --push needs --apply\n")
        return EXIT_USAGE
    date = args.date or dt.datetime.now(dt.UTC).date().isoformat()
    release = Release(
        args.version, date, args.root, args.apply, args.push, not args.no_gate
    )
    try:
        cut(release)
    except ReleaseError as error:
        sys.stderr.write(f"release: {error}\n")
        return EXIT_FAILED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
