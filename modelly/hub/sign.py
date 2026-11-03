"""Signing and verifying hub packages with Sigstore, through the ``sigstore`` command.

Signing opens a browser for the publisher to log in (Sigstore's keyless signing: the
signature binds the file to that identity, recorded in a public transparency log), so it is
something the publisher runs, never a test. ``sign(path, dry_run=True)`` returns the command
without running it. Verification needs the identity and issuer the index records. Without
the ``sigstore`` package (``pip install sigstore``), verification is skipped with a warning,
since the sha256 in the index has already been checked.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

from modelly.hub.index import HubError

SUFFIX = ".sigstore.json"


def available() -> bool:
    """Whether the ``sigstore`` package is installed."""
    return importlib.util.find_spec("sigstore") is not None


def sign_command(path: Path) -> list[str]:
    """The command that signs ``path``, writing ``<path>.sigstore.json``."""
    bundle = Path(f"{path}{SUFFIX}")
    return [
        sys.executable,
        "-m",
        "sigstore",
        "sign",
        "--bundle",
        str(bundle),
        str(path),
    ]


def sign(
    path: Path, dry_run: bool = True, runner: Callable[..., Any] = subprocess.run
) -> tuple[list[str], Path | None]:
    """Sign ``path``: the command, and the bundle written (None on a dry run).

    Raises:
        HubError: when ``sigstore`` is missing or signing fails.
    """
    command = sign_command(path)
    if dry_run:
        return command, None
    if not available():
        raise HubError("signing needs the sigstore package: pip install sigstore")
    if runner(command, check=False).returncode != 0:
        raise HubError(f"sigstore could not sign {path}")
    return command, Path(f"{path}{SUFFIX}")


def verify(
    path: Path, bundle: Path, signature: Any, runner: Callable[..., Any]
) -> bool:
    """Check ``path`` against its Sigstore ``bundle``; False when sigstore is missing.

    Raises:
        HubError: when the signature does not verify for the recorded identity.
    """
    if not available():
        warnings.warn(
            f"{path.name} is signed but sigstore is not installed; only its sha256 was "
            "checked (pip install sigstore to verify signatures)",
            RuntimeWarning,
            stacklevel=2,
        )
        return False
    command = [sys.executable, "-m", "sigstore", "verify", "identity", "--bundle", str(bundle),
               "--cert-identity", signature.identity, "--cert-oidc-issuer", signature.issuer,
               str(path)]  # fmt: skip
    done = runner(command, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise HubError(f"the signature of {path.name} does not verify:\n{done.stderr}")
    return True
