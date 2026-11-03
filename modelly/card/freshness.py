"""Is a card complete, and was its validation run on the model as it is now?

The stamp of a card records a digest of the model's source files when its validation tests
last passed (``stamp``). ``problems`` compares it with the source today: a model changed
since is *stale* until its validation runs again. The digest reads the files with their
line endings made LF, so a checkout on Windows gives the digest written on Linux.
"""

from __future__ import annotations

import datetime
import importlib.util
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import modelly
from modelly.card.schema import SECTIONS, TODO, ModelCard, Stamp, read_card, write_card
from modelly.provenance.files import hash_bytes, hash_mapping, relative_posix


def source_files(card: ModelCard, folder: Path) -> list[Path]:
    """The files the validation depends on: the ``sources`` globs, or the model's module."""
    if card.sources:
        found = {p for pattern in card.sources for p in Path(folder).glob(pattern)}
        return sorted(p for p in found if p.is_file())
    module = card.model.rpartition(":")[0]
    if module.endswith(".py"):  # a model file, relative to the card
        path = Path(folder) / module
        return [path] if path.is_file() else []
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError):
        spec = None
    origin = getattr(spec, "origin", None)
    return [Path(origin)] if origin and Path(origin).is_file() else []


def source_digest(card: ModelCard, folder: Path) -> str:
    """``sha256:<hex>`` over the source files' names and LF-normalised contents."""
    hashes = {
        relative_posix(path, folder): hash_bytes(
            path.read_bytes().replace(b"\r\n", b"\n")
        )
        for path in source_files(card, folder)
    }
    return hash_mapping(hashes)


def _incomplete(card: ModelCard) -> list[str]:
    """The sections that are empty or still hold a TODO marker."""
    found = []
    texts = {
        "summary": (card.summary,),
        **{key: getattr(card, key) for key, _ in SECTIONS},
    }
    texts["validation"] = tuple(f"{c.check} {c.test}" for c in card.validation)
    for key, items in texts.items():
        if not items or not any(item.strip() for item in items):
            found.append(f"{key} is empty")
        elif any(TODO in item for item in items):
            found.append(f"{key} still has a {TODO}")
    return found


def problems(card: ModelCard, folder: Path) -> list[str]:
    """What is wrong with ``card`` (in ``folder``); empty when it is complete and fresh."""
    found = _incomplete(card)
    if not source_files(card, folder):
        found.append(f"no source file found for {card.model}")
    elif card.validated is None:
        found.append("never validated: run `modelly card stamp`")
    elif card.validated.source != source_digest(card, folder):
        found.append(
            f"stale: the model changed since its validation passed on "
            f"{card.validated.date}; run `modelly card stamp` again"
        )
    return found


def stamp(
    path: Path, root: Path, today: datetime.date | None = None
) -> tuple[bool, str]:
    """Run the card's validation tests from ``root``; on success, stamp the card.

    Returns:
        Whether the tests passed (the card is written only then) and pytest's output.
    """
    card = read_card(path)
    if not card.validation:
        return False, "the card lists no validation test"
    tests = sorted({check.test for check in card.validation})
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests],
        cwd=root, capture_output=True, text=True, check=False,
    )  # fmt: skip
    if run.returncode != 0:
        return False, run.stdout + run.stderr
    date = (today or datetime.datetime.now(datetime.UTC).date()).isoformat()
    digest = source_digest(card, Path(path).parent)
    write_card(replace(card, validated=Stamp(digest, modelly.__version__, date)), path)
    return True, run.stdout
