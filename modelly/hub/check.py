"""The checks every index change passes before it is merged (the hub repository runs them).

``check_index(path)`` reads an index and reports, per entry: the schema, a unique name, a
``modelly`` specifier that parses, a model card with every section and a validation stamp,
and, with ``download=True``, that each file the entry points to has the sha256 it records.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from modelly._versions import satisfies
from modelly.card.schema import SECTIONS
from modelly.hub.entry import SCHEMA, check
from modelly.hub.index import HubError
from modelly.hub.install import download


def _card(card: dict[str, Any]) -> list[str]:
    """Problems of an entry's card: a section empty, no validation, no stamp."""
    found = [f"card: {key} is empty" for key, _ in SECTIONS if not card.get(key)]
    if not card.get("validation"):
        found.append("card: no validation test")
    if not card.get("validated"):
        found.append("card: validation never stamped")
    return found


def _files(entry: dict[str, Any], folder: Path) -> list[str]:
    """Download every file of the entry and check its hash."""
    items = [
        entry.get("source", {}),
        entry.get("bundle") or {},
        entry.get("signature") or {},
    ]
    found = []
    for item in (i for i in items if i.get("url")):
        try:
            download(item["url"], item.get("sha256", ""), folder)
        except (HubError, OSError) as problem:
            found.append(str(problem))
    return found


def check_entry(entry: dict[str, Any], download_files: bool = False) -> list[str]:
    """Every problem of one entry."""
    found = check(entry)
    try:
        satisfies("1.0.0", str(entry.get("modelly", "")))
    except ValueError as problem:
        found.append(f"modelly: {problem}")
    found += _card(entry.get("card") or {})
    if download_files and not found:
        with tempfile.TemporaryDirectory() as folder:
            found += _files(entry, Path(folder))
    return found


def check_index(path: Path, download_files: bool = False) -> dict[str, list[str]]:
    """The problems of each entry of the index at ``path``, by name (``""`` for the index)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    report: dict[str, list[str]] = {}
    if data.get("schema") != SCHEMA or not isinstance(data.get("models"), list):
        return {"": [f"not an index of schema {SCHEMA} with a models list"]}
    names = [m.get("name") for m in data["models"]]
    for entry in data["models"]:
        found = check_entry(entry, download_files)
        if names.count(entry.get("name")) > 1:
            found.append("the name is used twice")
        if found:
            report[str(entry.get("name"))] = found
    return report
