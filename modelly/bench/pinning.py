"""Pinning the benchmark runs to one CPU core, where the operating system allows it.

Pure Python through ``psutil.Process().cpu_affinity``: Linux and Windows support
it, macOS has no affinity API and runs stay unpinned (the report says so). The
benchmark pins its own process before starting a run; the run's interpreter
inherits the affinity on both systems.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Pinning:
    """Where the runs go: ``core`` is None when they are not pinned, and ``note`` says why."""

    core: int | None
    note: str


def _process() -> Any:
    """This process as a psutil.Process, or None when psutil is not installed."""
    try:
        import psutil  # noqa: PLC0415 - optional dependency
    except ImportError:
        return None
    return psutil.Process()


def choose(requested: int | None, enabled: bool = True) -> Pinning:
    """The core to pin to: ``requested``, else the last one this process may use."""
    if not enabled:
        return Pinning(None, "not pinned (--no-pin)")
    if sys.platform == "darwin":
        return Pinning(None, "not pinned: macOS has no CPU affinity API")
    process = _process()
    if process is None:
        return Pinning(
            None, "not pinned: psutil is not installed (pip install modelly-abm[bench])"
        )
    if not hasattr(process, "cpu_affinity"):
        return Pinning(None, f"not pinned: no CPU affinity API on {sys.platform}")
    allowed = process.cpu_affinity()
    if requested is not None and requested not in allowed:
        raise ValueError(
            f"core {requested} is not one of this process's cores {allowed}"
        )
    core = requested if requested is not None else allowed[-1]
    return Pinning(core, f"pinned to core {core} (psutil cpu_affinity)")


@contextmanager
def pinned(pinning: Pinning) -> Iterator[None]:
    """Run the body with this process (and the processes it starts) on ``pinning.core``."""
    if pinning.core is None:
        yield
        return
    process = _process()
    before = process.cpu_affinity()
    process.cpu_affinity([pinning.core])
    try:
        yield
    finally:
        process.cpu_affinity(before)
