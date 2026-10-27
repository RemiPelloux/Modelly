"""The benchmark history: one JSON line per ``modelly bench`` run, and the regression check.

Each line records when and where it ran (Modelly version, compiled or pure
modules, Python, platform, pinning), the size, seed and rounds, and per
``playbook/variant`` every round's CPU seconds and their median. Lines are only
ever appended, so the file is the full record.
"""

from __future__ import annotations

import datetime
import json
import platform
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import modelly

SCHEMA = 1
DEFAULT_HISTORY = Path(".modelly-bench") / "history.jsonl"
DEFAULT_THRESHOLD = 0.10


def native_modules() -> dict[str, bool]:
    """Which compiled modules this interpreter uses (False: the pure-Python twin)."""
    from modelly._native import cells, events, loops, sets  # noqa: PLC0415 - the core
    from modelly.core import rng  # noqa: PLC0415

    return {
        "fastrng": rng.NATIVE,
        "fastloop": loops.NATIVE,
        "fastcell": cells.NATIVE,
        "fastset": sets.NATIVE,
        "fastevents": events.NATIVE,
    }


def make_entry(
    runs: dict[str, list[dict[str, Any]]], settings: dict[str, Any]
) -> dict[str, Any]:
    """One history line from the RESULT rows of every round, by ``playbook/variant``."""
    results = {}
    for key, rows in runs.items():
        cpu = [row["cpu_seconds"] for row in rows]
        results[key] = {
            "cpu_seconds": cpu,
            "median": statistics.median(cpu),
            "population": rows[-1].get("population"),
        }
    return {
        "schema": SCHEMA,
        "time": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "modelly": modelly.__version__,
        "native": native_modules(),
        "python": platform.python_version(),
        "implementation": sys.implementation.name,
        "platform": platform.platform(),
        "machine": platform.machine(),
        **settings,
        "results": results,
    }


def append(path: Path, entry: dict[str, Any]) -> None:
    """Add ``entry`` as the last line of ``path`` (created with its folder if needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def load(path: Path) -> list[dict[str, Any]]:
    """Every entry of the history file, oldest first; empty when there is none."""
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def find_baseline(
    entries: list[dict[str, Any]], wanted: str | None, size: str
) -> dict[str, Any] | None:
    """The entry to compare with: by label, by index (``0``, ``-2``), else the latest at ``size``."""
    if wanted is None:
        same = [entry for entry in entries if entry.get("size") == size]
        return same[-1] if same else None
    labelled = [entry for entry in entries if entry.get("label") == wanted]
    if labelled:
        return labelled[-1]
    try:
        return entries[int(wanted)]
    except (ValueError, IndexError):
        raise LookupError(f"no history entry labelled or numbered {wanted!r}") from None


@dataclass(frozen=True)
class Change:
    """One variant's median against the baseline's: ``ratio`` > 1 is slower."""

    key: str
    median: float
    baseline: float | None
    ratio: float | None
    regression: bool


def compare(
    entry: dict[str, Any], baseline: dict[str, Any] | None, threshold: float
) -> list[Change]:
    """Each variant of ``entry`` against ``baseline``; a regression is slower by more than ``threshold``."""
    old = baseline["results"] if baseline else {}
    changes = []
    for key, result in entry["results"].items():
        before = old.get(key, {}).get("median")
        ratio = result["median"] / before if before else None
        slower = ratio is not None and ratio > 1.0 + threshold
        changes.append(Change(key, result["median"], before, ratio, slower))
    return changes
