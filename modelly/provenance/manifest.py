"""The run manifest: a versioned JSON record of what produced a set of outputs.

``format`` names the schema and its major version (``modelly-manifest/1``). A reader
accepts any manifest of the same major version and refuses others, so fields can be
added without breaking old readers. Paths are relative to the manifest's folder and
written with forward slashes; hashes are ``sha256:<hex>`` over bytes.

Top-level fields (all present in version 1)::

    format       the schema name and version
    target       {"kind": "file" | "module", "source", "class"}; a file source is
                 relative to code.root
    code         {"root", "files": {path: hash}, "hash", "git": {"commit", "dirty",
                 "diff_hash"} | null}
    environment  {"modelly": {"version", "build", "native"}, "python", "platform",
                 "dependencies": {name: version}, "packages": {name: version}}
    scenario     {"file", "hash", "parameters", "resolved"}
    run          {"steps", "seed"}
    seeds        {"seed", "entropy", "spawn_key", "stdlib_seed"}
    inputs       [{"path", "hash"}]
    outputs      [{"table", "path", "format", "hash", "rows", "columns"}]
    timing       {"wall_seconds", "cpu_seconds"}

Optional fields (added within version 1, absent when they do not apply)::

    llm_cache    {"path", "hash", "responses"}: the replies of the model's
                 language-model clients, replayed by ``modelly verify``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from modelly.provenance.files import read_json, write_json_atomic

FORMAT_NAME = "modelly-manifest"
FORMAT_VERSION = 1
FORMAT = f"{FORMAT_NAME}/{FORMAT_VERSION}"
MANIFEST_NAME = "manifest.json"
REQUIRED = (
    "code",
    "environment",
    "format",
    "inputs",
    "outputs",
    "run",
    "scenario",
    "seeds",
    "target",
    "timing",
)


class ManifestError(ValueError):
    """A manifest that cannot be read, or one written in an unsupported format."""


def json_safe(value: Any) -> Any:
    """``value`` if JSON can hold it, else its ``repr`` (documents, never re-reads)."""
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return repr(value)
    return value


def manifest_path(path: Path) -> Path:
    """``path`` itself, or the manifest inside it when ``path`` is a run folder."""
    path = Path(path)
    return path / MANIFEST_NAME if path.is_dir() else path


def check_format(record: Any) -> None:
    """Raise ManifestError unless ``record`` is a version-1 manifest with every field."""
    if not isinstance(record, dict):
        raise ManifestError("a manifest is a JSON object")
    name, _, version = str(record.get("format", "")).partition("/")
    if name != FORMAT_NAME or version != str(FORMAT_VERSION):
        raise ManifestError(
            f"unsupported manifest format {record.get('format')!r} (this Modelly reads {FORMAT})"
        )
    missing = [key for key in REQUIRED if key not in record]
    if missing:
        raise ManifestError(f"manifest lacks {', '.join(missing)}")


def read_manifest(path: Path) -> dict:
    """The manifest at ``path`` (a file or a run folder), checked against the schema."""
    path = manifest_path(path)
    try:
        record = read_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ManifestError(f"cannot read {path}: {error}") from error
    check_format(record)
    return record


def write_manifest(folder: Path, record: dict) -> Path:
    """Check and write ``record`` as ``folder/manifest.json`` atomically; its path."""
    check_format(record)
    path = Path(folder) / MANIFEST_NAME
    write_json_atomic(path, record)
    return path
