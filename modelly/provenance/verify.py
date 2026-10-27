"""Rerun a recorded run from its manifest and compare the new outputs with the old.

The rerun uses the manifest's target, parameters, seed and step count, writes its
outputs to a temporary folder in the recorded formats, reads both sets back and reports
the first table, column and row where they differ. Changes that do not stop the rerun
(code files, input files or the environment differ from the record) are notes.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from modelly.core.model import Model
from modelly.profile.loader import load_class
from modelly.provenance.code import changed_files
from modelly.provenance.compare import Difference, Tolerance, first_difference
from modelly.provenance.environment import modelly_info, python_info
from modelly.provenance.files import from_posix, hash_file
from modelly.provenance.manifest import manifest_path, read_manifest
from modelly.provenance.outputs import collected_tables, read_table, write_tables
from modelly.provenance.runner import execute


@dataclass
class Verification:
    """The outcome of :func:`verify`: the first difference (None if all match) and notes."""

    difference: Difference | None
    notes: list[str] = field(default_factory=list)

    @property
    def matches(self) -> bool:
        """True when every recorded output was reproduced."""
        return self.difference is None


def code_root(manifest: dict[str, Any], folder: Path) -> Path:
    """The folder the manifest's code paths are relative to."""
    return from_posix(manifest["code"]["root"], folder)


def target_class(manifest: dict[str, Any], folder: Path) -> type[Model[Any, Any]]:
    """Load the model class the manifest records."""
    target = manifest["target"]
    source = target["source"]
    if target["kind"] == "file":
        source = str(code_root(manifest, folder) / source)
    return load_class(f"{source}:{target['class']}")


def record_notes(manifest: dict[str, Any], folder: Path) -> list[str]:
    """What differs between the record and this machine, short of the outputs."""
    notes = [
        f"code file changed or missing: {name}"
        for name in changed_files(
            code_root(manifest, folder), manifest["code"]["files"]
        )
    ]
    for item in manifest["inputs"]:
        path = from_posix(item["path"], folder)
        if not path.is_file() or hash_file(path) != item["hash"]:
            notes.append(f"input file changed or missing: {item['path']}")
    recorded = manifest["environment"]
    for label, now in (("modelly", modelly_info()), ("python", python_info())):
        if recorded[label]["version"] != now["version"]:
            notes.append(
                f"{label} {now['version']} here, {recorded[label]['version']} in the record"
            )
    return notes


def rerun_tables(
    manifest: dict[str, Any], folder: Path, scratch: Path
) -> dict[str, tuple[Path, str]]:
    """Rerun the model and write its outputs to ``scratch``; table name to (file, format)."""
    cls = target_class(manifest, folder)
    run = manifest["run"]
    params = dict(manifest["scenario"]["parameters"])
    model = execute(cls, params, run["seed"], run["steps"])
    forms = {item["table"]: item["format"] for item in manifest["outputs"]}
    written = write_tables(collected_tables(model), scratch, forms)
    return {item["table"]: (scratch / item["path"], item["format"]) for item in written}


def compare_outputs(
    manifest: dict[str, Any], folder: Path, fresh: dict[str, Any], tolerance: Tolerance
) -> Difference | None:
    """The first difference between the recorded outputs and the fresh ones."""
    for item in manifest["outputs"]:
        name = item["table"]
        recorded = from_posix(item["path"], folder)
        if not recorded.is_file():
            return Difference(name, f"recorded output {item['path']} is missing")
        if name not in fresh:
            return Difference(name, "the rerun did not produce this table")
        path, form = fresh[name]
        difference = first_difference(
            name,
            read_table(recorded, item["format"]),
            read_table(path, form),
            tolerance,
        )
        if difference is not None:
            return difference
    extra = sorted(set(fresh) - {item["table"] for item in manifest["outputs"]})
    return (
        Difference(extra[0], "the rerun produced a table the record lacks")
        if extra
        else None
    )


def verify(path: Path, tolerance: Tolerance | None = None) -> Verification:
    """Rerun the manifest at ``path`` (a file or run folder) and compare outputs.

    Raises ManifestError for an unreadable manifest and TargetError when the model
    cannot be loaded; anything the model raises propagates.
    """
    path = manifest_path(path)
    manifest = read_manifest(path)
    folder = path.parent
    notes = record_notes(manifest, folder)
    with tempfile.TemporaryDirectory(prefix="modelly-verify-") as scratch:
        fresh = rerun_tables(manifest, folder, Path(scratch))
        difference = compare_outputs(manifest, folder, fresh, tolerance or Tolerance())
    return Verification(difference, notes)
