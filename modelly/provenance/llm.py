"""The language-model replies of a recorded run, so a rerun needs no network.

``modelly run`` exports the replies every :class:`modelly.llm.Client` of the model
holds (its attributes, ``model.llm`` by convention) to ``llm-responses.jsonl.gz``
next to the outputs, and records it in the manifest as ``llm_cache``
(``{"path", "hash", "responses"}``). ``modelly bundle`` packs that file, and
``modelly verify`` reruns the model inside ``modelly.llm.replay.replaying`` so every
client answers from it, read-only: the study verifies offline, and a call the record
does not hold stops the rerun with ``CacheMiss``. A run without a client records
nothing and its manifest has no ``llm_cache``.
"""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Any

from modelly.llm.cache import ResponseCache
from modelly.llm.client import Client
from modelly.llm.replay import replaying
from modelly.provenance.files import from_posix, hash_file

CACHE_FILE = "llm-responses.jsonl.gz"
FIELD = "llm_cache"


def model_clients(model: Any) -> list[Client]:
    """The distinct clients among the model's attributes, in attribute order."""
    found: dict[int, Client] = {}
    for value in vars(model).values():
        if isinstance(value, Client):
            found.setdefault(id(value), value)
    return list(found.values())


def cache_record(model: Any, out: Path) -> dict[str, Any] | None:
    """Export the replies of the model's clients to ``out``; the manifest entry.

    Returns:
        ``{"path", "hash", "responses"}``, or None when the model has no client.
    """
    clients = model_clients(model)
    if not clients:
        return None
    merged = ResponseCache()
    for client in clients:
        merged.insert(list(client.cache.rows()))
    path = merged.export(Path(out) / CACHE_FILE)
    return {"hash": hash_file(path), "path": CACHE_FILE, "responses": len(merged)}


def cache_problem(manifest: dict[str, Any], folder: Path) -> str | None:
    """Why the recorded cache cannot be used as recorded, or None if it can."""
    record = manifest.get(FIELD)
    if record is None:
        return None
    path = from_posix(record["path"], folder)
    if not path.is_file():
        return f"language-model cache {record['path']} is missing"
    if hash_file(path) != record["hash"]:
        return f"language-model cache {record['path']} changed since the run"
    return None


def replay_for(
    manifest: dict[str, Any], folder: Path
) -> AbstractContextManager[object]:
    """Replay the run's recorded replies, or nothing when there are none to replay."""
    record = manifest.get(FIELD)
    path = None if record is None else from_posix(record["path"], folder)
    if path is None or not path.is_file():
        return nullcontext()
    return replaying(path)
