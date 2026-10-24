"""Pack a recorded run into one deterministic zip a reviewer can verify.

The archive holds the manifest (its paths rewritten for the archive layout), the
outputs, the model's source files under ``code/``, the input files under ``inputs/``,
``requirements.lock``, ``seeds.json``, Zenodo metadata (``.zenodo.json``) and a
``CITATION.cff`` stub. Entries are sorted, stored uncompressed and stamped with a fixed
time and mode, so the same run gives the same bytes on every machine.
"""

from __future__ import annotations

import copy
import io
import zipfile
from pathlib import Path

from modelly.provenance.code import changed_files
from modelly.provenance.environment import lock_text
from modelly.provenance.files import (
    dump_json,
    from_posix,
    hash_file,
    write_bytes_atomic,
)
from modelly.provenance.manifest import MANIFEST_NAME, manifest_path, read_manifest
from modelly.provenance.metadata import citation_cff, zenodo_metadata

CODE_DIR, INPUTS_DIR = "code", "inputs"
# The earliest time a zip entry can carry (1980-01-01): no clock leaks into the bytes.
FIXED_TIME = (1980, 1, 1, 0, 0, 0)
FILE_MODE = 0o100644
MODE_SHIFT = 16
UNIX_SYSTEM = 3


class BundleError(ValueError):
    """The run folder does not hold what its manifest records."""


def _check_unchanged(manifest: dict, folder: Path) -> None:
    """Raise BundleError if outputs or code changed since the run."""
    for item in manifest["outputs"]:
        path = from_posix(item["path"], folder)
        if not path.is_file() or hash_file(path) != item["hash"]:
            raise BundleError(f"output {item['path']} changed since the run: rerun it")
    root = from_posix(manifest["code"]["root"], folder)
    changed = changed_files(root, manifest["code"]["files"])
    if changed:
        raise BundleError(f"code changed since the run: {', '.join(changed)}")


def _input_entries(manifest: dict, folder: Path, entries: dict) -> dict:
    """Copy inputs and the scenario file into ``inputs/``; the rewritten manifest."""
    packed = copy.deepcopy(manifest)
    items = list(packed["inputs"])
    scenario = packed["scenario"]
    if scenario.get("file"):
        items.append(scenario)
    for item in items:
        key = "file" if item is scenario else "path"
        name = f"{INPUTS_DIR}/{Path(item[key]).name}"
        if name in entries:
            raise BundleError(f"two inputs are named {Path(item[key]).name}")
        entries[name] = from_posix(item[key], folder).read_bytes()
        item[key] = name
    return packed


def bundle_entries(folder: Path) -> dict[str, bytes]:
    """Archive name to bytes for the run recorded in ``folder``."""
    path = manifest_path(folder)
    manifest = read_manifest(path)
    folder = path.parent
    _check_unchanged(manifest, folder)
    entries: dict[str, bytes] = {}
    for item in manifest["outputs"]:
        entries[item["path"]] = from_posix(item["path"], folder).read_bytes()
    root = from_posix(manifest["code"]["root"], folder)
    for name in manifest["code"]["files"]:
        entries[f"{CODE_DIR}/{name}"] = root.joinpath(*name.split("/")).read_bytes()
    packed = _input_entries(manifest, folder, entries)
    packed["code"]["root"] = CODE_DIR
    entries[MANIFEST_NAME] = dump_json(packed)
    entries["requirements.lock"] = lock_text(
        manifest["environment"]["packages"]
    ).encode("utf-8")
    entries["seeds.json"] = dump_json(
        {**manifest["seeds"], "steps": manifest["run"]["steps"]}
    )
    entries[".zenodo.json"] = dump_json(zenodo_metadata(manifest))
    entries["CITATION.cff"] = citation_cff(manifest).encode("utf-8")
    return entries


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    """A zip of ``entries``: sorted, stored, fixed time and mode (reproducible bytes)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
            info.create_system = UNIX_SYSTEM
            info.external_attr = FILE_MODE << MODE_SHIFT
            archive.writestr(info, entries[name])
    return buffer.getvalue()


def bundle(folder: Path, out: Path) -> Path:
    """Write the bundle of the run in ``folder`` (or of a manifest path) to ``out``.

    Raises ManifestError for an unreadable manifest and BundleError when outputs or
    code changed since the run.
    """
    write_bytes_atomic(Path(out), zip_bytes(bundle_entries(Path(folder))))
    return Path(out)
