"""Byte hashes, portable relative paths and atomic writes for provenance records.

Hashes are taken over file bytes, never over decoded text, so the same file gives the
same hash on every operating system. Paths written to a manifest are relative and use
forward slashes; they are turned back into native paths with :func:`from_posix`.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any

HASH_NAME = "sha256"
CHUNK_BYTES = 1 << 20
JSON_INDENT = 2


def hash_bytes(data: bytes) -> str:
    """``sha256:<hex>`` of ``data``."""
    return f"{HASH_NAME}:{hashlib.sha256(data).hexdigest()}"


def hash_file(path: Path) -> str:
    """``sha256:<hex>`` of the bytes of ``path``, read in chunks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return f"{HASH_NAME}:{digest.hexdigest()}"


def hash_mapping(hashes: dict[str, str]) -> str:
    """One hash for a set of named hashes, independent of their insertion order."""
    lines = "".join(f"{name}\0{value}\n" for name, value in sorted(hashes.items()))
    return hash_bytes(lines.encode("utf-8"))


def relative_posix(path: Path, start: Path) -> str:
    """``path`` relative to ``start`` with forward slashes.

    Falls back to the absolute path when the two share no root (another drive on
    Windows), so the record stays usable on the machine that wrote it.
    """
    path, start = Path(path).resolve(), Path(start).resolve()
    try:
        return Path(os.path.relpath(path, start)).as_posix()
    except ValueError:
        return path.as_posix()


def from_posix(text: str, start: Path) -> Path:
    """The native path a manifest's POSIX ``text`` names, relative to ``start``."""
    posix = PurePosixPath(text)
    if posix.is_absolute() or Path(text).is_absolute():
        return Path(text)
    return Path(start).joinpath(*posix.parts)


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` through a sibling temporary file and ``os.replace``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def dump_json(record: Any) -> bytes:
    """``record`` as UTF-8 JSON with sorted keys and a final newline (stable bytes)."""
    text = json.dumps(record, indent=JSON_INDENT, sort_keys=True, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def write_json_atomic(path: Path, record: Any) -> None:
    """Write ``record`` as stable JSON to ``path`` atomically."""
    write_bytes_atomic(path, dump_json(record))


def read_json(path: Path) -> Any:
    """The JSON document at ``path``, read as UTF-8."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
