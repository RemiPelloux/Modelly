"""Checkpoints of a split run: one file per partition plus an index.

``part-00003.ckpt`` holds partition 3: a short header line and a pickle of its
index, its layout and its model as a core checkpoint (``checkpoint_bytes``, so
the Modelly and Python versions are checked the same way). ``index.json`` names
the model class, the number of partitions, the time, the reporter rows so far
and each file with its SHA-256; a restore checks every file against it.

Security: the files are pickles; only restore checkpoints you wrote or trust.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import pickle
from pathlib import Path
from typing import Any

import modelly
from modelly.core.checkpoint import checkpoint_bytes, model_from_bytes
from modelly.core.exceptions import CheckpointError

MAGIC = b"MODELLY-PARTITION\n"
INDEX = "index.json"
FORMAT = 1
PART_NAME = "part-{:05d}.ckpt"
PROTOCOL = pickle.HIGHEST_PROTOCOL


def digest(path: Path) -> str:
    """The SHA-256 of a file, in hex."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_part(directory: Path, index: int, model: Any, layout: Any) -> dict:
    """Write partition ``index``; its entry for the index."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / PART_NAME.format(index)
    payload = {"index": index, "layout": layout, "model": checkpoint_bytes(model)}
    path.write_bytes(MAGIC + pickle.dumps(payload, protocol=PROTOCOL))
    return {"partition": index, "file": path.name, "sha256": digest(path)}


def read_part(path: Path, expected: str | None) -> tuple[int, Any, Any]:
    """``(index, layout, model)`` of a partition file, checked against its digest.

    Raises:
        CheckpointError: when the file is not a partition checkpoint or has changed.
    """
    data = path.read_bytes()
    if not data.startswith(MAGIC):
        raise CheckpointError(f"{path} is not a Modelly partition checkpoint")
    if expected is not None and hashlib.sha256(data).hexdigest() != expected:
        raise CheckpointError(f"{path} does not match the digest in its index")
    payload = pickle.loads(data[len(MAGIC) :])  # noqa: S301 - see the module warning
    model = model_from_bytes(payload["model"], str(path))
    return payload["index"], payload["layout"], model


def class_path(model_class: type) -> str:
    """``module:QualName`` of a class."""
    return f"{model_class.__module__}:{model_class.__qualname__}"


def load_class(path: str) -> type:
    """The class named by ``class_path``."""
    module, _, name = path.partition(":")
    target: Any = importlib.import_module(module)
    for part in name.split("."):
        target = getattr(target, part)
    return target


def write_index(directory: Path, model_class: type, rows: list, files: list) -> Path:
    """Write ``index.json`` for the partition files ``files``."""
    index = {
        "format": FORMAT,
        "modelly": modelly.__version__,
        "model": class_path(model_class),
        "partitions": len(files),
        "time": rows[-1]["time"] if rows else 0.0,
        "rows": rows,
        "files": sorted(files, key=lambda entry: entry["partition"]),
    }
    path = Path(directory) / INDEX
    path.write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    return path


def read_index(directory: str | Path) -> dict:
    """The index of a split-run checkpoint.

    Raises:
        CheckpointError: when there is no index, or one of another format.
    """
    path = Path(directory) / INDEX
    if not path.exists():
        raise CheckpointError(f"{directory} holds no {INDEX}")
    index = json.loads(path.read_text(encoding="utf-8"))
    if index.get("format") != FORMAT:
        raise CheckpointError(f"{path} has format {index.get('format')}, not {FORMAT}")
    return index
