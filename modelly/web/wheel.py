"""The pure-Python wheel of Modelly a static site ships for Pyodide.

``write_wheel`` packs the installed ``modelly`` package, without its compiled modules (the
pure-Python twins replace them), its C sources and the parts that cannot run in a browser
tab or that a model does not import (``EXCLUDED``: the command-line tools, Solara
visualisation, the examples). An example model's own folder is kept, so an exported
example finds its code. The wheel is deterministic: same files, same bytes.
"""

from __future__ import annotations

import base64
import hashlib
import zipfile
from pathlib import Path, PurePosixPath

import modelly

DISTRIBUTION = "modelly_abm"
TAG = "py3-none-any"
# Top-level parts of the package a browser model never imports.
EXCLUDED = frozenset(
    {"bench", "dev", "examples", "lint", "new", "viz", "migrate.py", "migrate_rules.py"}
)
SKIPPED_SUFFIXES = frozenset({".c", ".h", ".so", ".pyd", ".pyc"})
# Every entry gets this timestamp, so the wheel's bytes depend on its files only.
FIXED_DATE = (2020, 1, 1, 0, 0, 0)
WHEEL_METADATA = "Wheel-Version: 1.0\nGenerator: modelly export-web\nRoot-Is-Purelib: true\nTag: {tag}\n"
METADATA = "Metadata-Version: 2.1\nName: modelly-abm\nVersion: {version}\n"


def package_root() -> Path:
    """The folder of the installed ``modelly`` package."""
    return Path(modelly.__file__).parent


def wheel_name(version: str = modelly.__version__) -> str:
    """The file name of the browser wheel of ``version``."""
    return f"{DISTRIBUTION}-{version}-{TAG}.whl"


def _kept(relative: PurePosixPath, keep: PurePosixPath | None) -> bool:
    """Whether the file ``relative`` (to the package root) goes into the wheel."""
    if "__pycache__" in relative.parts or relative.suffix in SKIPPED_SUFFIXES:
        return False
    if relative.parts[0] not in EXCLUDED:
        return True
    if keep is None:
        return False
    inside = relative.parts[: len(keep.parts)] == keep.parts
    # The __init__.py files of the folders above the kept one make it importable.
    above = relative.name == "__init__.py" and relative.parent in keep.parents
    return inside or above


def package_files(keep: PurePosixPath | None = None) -> list[PurePosixPath]:
    """The package's files the wheel holds, relative to its root, sorted.

    Args:
        keep: A folder under an excluded part (``examples/basic/schelling``) to keep.
    """
    root = package_root()
    found = (
        PurePosixPath(path.relative_to(root).as_posix())
        for path in root.rglob("*")
        if path.is_file()
    )
    return sorted(path for path in found if _kept(path, keep))


def _record_line(name: str, data: bytes) -> str:
    """The RECORD line of one file: its path, sha256 and size."""
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return f"{name},sha256={digest.decode()},{len(data)}"


def _add(archive: zipfile.ZipFile, name: str, data: bytes) -> str:
    """Store ``data`` as ``name`` with the fixed timestamp; its RECORD line."""
    info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)
    return _record_line(name, data)


def write_wheel(out_dir: Path, keep: PurePosixPath | None = None) -> Path:
    """Write the browser wheel into ``out_dir``; its path."""
    version = modelly.__version__
    info = f"{DISTRIBUTION}-{version}.dist-info"
    path = out_dir / wheel_name(version)
    out_dir.mkdir(parents=True, exist_ok=True)
    root = package_root()
    with zipfile.ZipFile(path, "w") as archive:
        record = [
            _add(archive, f"modelly/{rel}", (root / rel).read_bytes())
            for rel in package_files(keep)
        ]
        record.append(
            _add(archive, f"{info}/METADATA", METADATA.format(version=version).encode())
        )
        record.append(
            _add(archive, f"{info}/WHEEL", WHEEL_METADATA.format(tag=TAG).encode())
        )
        record.append(f"{info}/RECORD,,")
        archive.writestr(
            zipfile.ZipInfo(f"{info}/RECORD", date_time=FIXED_DATE),
            "\n".join(record) + "\n",
        )
    return path


__all__ = ["package_files", "wheel_name", "write_wheel"]
