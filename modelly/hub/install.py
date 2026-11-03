"""Installing a hub model: check it supports this Modelly, fetch it, verify it, install it.

A zoo model is part of Modelly: installing it writes its module and README into a folder, as
``modelly zoo copy`` does. A package is installed with pip into the running environment:
from its ``url`` when the entry has one (downloaded, checked against its sha256 and, when the
entry is signed and ``sigstore`` is installed, against its signature, before pip sees it), or
from PyPI by its requirement. pip is run as ``python -m pip`` of the running interpreter, so
the model lands in the environment that runs Modelly, on every operating system.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import modelly
from modelly._versions import release, satisfies
from modelly.hub.entry import Artifact, HubEntry
from modelly.hub.index import TIMEOUT_SECONDS, HubError, cache_dir
from modelly.hub.sign import verify

type Runner = Callable[..., Any]
CHUNK = 1 << 20


@dataclass
class Installed:
    """What ``install`` did: the files written or fetched and the commands run."""

    entry: HubEntry
    files: list[Path] = field(default_factory=list)
    commands: list[list[str]] = field(default_factory=list)


def sha256_of(path: Path) -> str:
    """The hex sha256 of a file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, sha256: str, folder: Path) -> Path:
    """``url`` saved in ``folder``, checked against ``sha256``; a file path is copied.

    Raises:
        HubError: when the hash differs (the file is deleted).
    """
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / url.rstrip("/").rsplit("/", 1)[-1]
    if url.startswith(("http://", "https://")):
        with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as reply:
            path.write_bytes(reply.read())
    else:
        path.write_bytes(Path(url.removeprefix("file://")).read_bytes())
    if sha256_of(path) != sha256:
        path.unlink()
        raise HubError(
            f"{url} does not have the sha256 the index records; not installed"
        )
    return path


def compatible(entry: HubEntry) -> None:
    """Refuse an entry whose ``modelly`` specifier excludes the running Modelly."""
    if not satisfies(release(modelly.__version__), entry.modelly):
        raise HubError(
            f"{entry.name} supports Modelly {entry.modelly}, this is {modelly.__version__}"
        )


def _pip(target: str, runner: Runner) -> list[str]:
    """Run pip install on ``target``."""
    command = [sys.executable, "-m", "pip", "install", target]
    done = runner(command, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise HubError(f"pip could not install {target}:\n{done.stdout}{done.stderr}")
    return command


def _fetched(artifact: Artifact | None, folder: Path) -> Path | None:
    """The artifact downloaded and checked, or None."""
    return download(artifact.url, artifact.sha256, folder) if artifact else None


def install(
    entry: HubEntry, folder: Path | None = None, runner: Runner = subprocess.run
) -> Installed:
    """Install ``entry``: a zoo model into ``folder``, a package into this environment.

    Raises:
        HubError: for an incompatible Modelly, a bad hash or signature, or a pip failure.
    """
    compatible(entry)
    report = Installed(entry)
    if entry.kind == "zoo":
        from modelly.zoo.copy import copy_model  # noqa: PLC0415

        report.files = copy_model(entry.name, folder or Path(entry.name))
        return report
    if entry.source.url is None:
        report.commands.append(_pip(entry.source.requirement, runner))
        return report
    downloads = cache_dir() / "downloads" / entry.name
    package = download(entry.source.url, entry.source.sha256 or "", downloads)
    signature = _fetched(entry.signature, downloads)
    if signature is not None:
        verify(package, signature, entry.signature, runner)
    report.files = [p for p in (package, signature) if p is not None]
    report.commands.append(_pip(str(package), runner))
    return report
