"""The software environment a run happened in: Modelly build, Python, platform, packages."""

from __future__ import annotations

import importlib.metadata as metadata
import platform
import re

import modelly
from modelly._native import cells, loops
from modelly.core import rng

DISTRIBUTION = "modelly-abm"
# A requirement's project name, before any version specifier, extra or marker.
REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
NAME_SEPARATORS = re.compile(r"[-_.]+")


def canonical(name: str) -> str:
    """A distribution name normalised the way pip compares them (PEP 503)."""
    return NAME_SEPARATORS.sub("-", name).lower()


def native_flags() -> dict[str, bool]:
    """Which compiled cores are loaded: each falls back to its pure-Python twin."""
    return {"cells": cells.NATIVE, "loops": loops.NATIVE, "rng": rng.NATIVE}


def build_name(flags: dict[str, bool]) -> str:
    """``compiled`` when every core is native, ``pure`` when none is, else ``partial``."""
    if all(flags.values()):
        return "compiled"
    return "partial" if any(flags.values()) else "pure"


def modelly_info() -> dict:
    """Modelly's version and build (compiled or pure Python)."""
    flags = native_flags()
    return {"version": modelly.__version__, "build": build_name(flags), "native": flags}


def python_info() -> dict:
    """The interpreter: version and implementation."""
    return {
        "implementation": platform.python_implementation(),
        "version": platform.python_version(),
    }


def platform_info() -> dict:
    """The operating system and machine."""
    return {
        "machine": platform.machine(),
        "platform": platform.platform(),
        "system": platform.system(),
    }


def _installed_version(name: str) -> str | None:
    """The installed version of distribution ``name``, or None."""
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def dependency_versions() -> dict[str, str]:
    """Installed versions of the requirements of the modelly-abm distribution.

    Requirements of extras are left out; a requirement that is not installed (a
    platform-specific one) is skipped. Empty when Modelly runs from a source tree
    that was never installed.
    """
    try:
        requirements = metadata.requires(DISTRIBUTION) or []
    except metadata.PackageNotFoundError:
        return {}
    versions = {}
    for requirement in requirements:
        match = REQUIREMENT_NAME.match(requirement)
        if match is None or "extra ==" in requirement:
            continue
        version = _installed_version(match.group(1))
        if version is not None:
            versions[canonical(match.group(1))] = version
    return dict(sorted(versions.items()))


def installed_packages() -> dict[str, str]:
    """Every installed distribution and its version, like ``pip freeze``."""
    packages: dict[str, str] = {}
    for distribution in metadata.distributions():
        name = distribution.metadata["Name"]
        if name:
            packages.setdefault(canonical(name), distribution.version)
    return dict(sorted(packages.items()))


def lock_text(packages: dict[str, str]) -> str:
    """A ``name==version`` line per package, sorted: a pip-installable lock file."""
    return "".join(f"{name}=={version}\n" for name, version in sorted(packages.items()))


def environment() -> dict:
    """The manifest's environment block."""
    return {
        "dependencies": dependency_versions(),
        "modelly": modelly_info(),
        "packages": installed_packages(),
        "platform": platform_info(),
        "python": python_info(),
    }
