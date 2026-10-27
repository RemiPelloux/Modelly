"""Finding the playbooks and running one variant in a fresh interpreter.

A playbook directory (``benchmarks/playbooks`` in the Modelly repository) holds
``registry.py`` with a ``PLAYBOOKS`` dict and ``worker.py``, which runs one
variant and prints one ``RESULT {json}`` line with its CPU seconds. Every run
starts a new interpreter, so one run's caches and garbage never reach the next.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RESULT_PREFIX = "RESULT "
REGISTRY_FILE = "registry.py"
WORKER_FILE = "worker.py"
MODELLY_PREFIX = "modelly"
MESA_VARIANT = "mesa"
MESA_ENV = "MESA_PYTHON"


class PlaybookError(Exception):
    """The playbook directory, a name or a run is not usable; the message says why."""


@dataclass(frozen=True)
class Variant:
    """One implementation of one playbook, and the interpreter that runs it."""

    playbook: str
    name: str
    python: str

    @property
    def key(self) -> str:
        """``playbook/variant``, the name results are recorded under."""
        return f"{self.playbook}/{self.name}"


def load_registry(directory: Path) -> dict[str, Any]:
    """The ``PLAYBOOKS`` dict of ``directory/registry.py``."""
    path = directory / REGISTRY_FILE
    if not path.is_file() or not (directory / WORKER_FILE).is_file():
        raise PlaybookError(
            f"{directory} has no {REGISTRY_FILE} and {WORKER_FILE} (use --playbooks DIR)"
        )
    spec = importlib.util.spec_from_file_location("modelly_bench_registry", path)
    assert spec is not None and spec.loader is not None  # a .py path always has both
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    playbooks: dict[str, Any] = module.PLAYBOOKS
    return playbooks


def select_variants(
    registry: dict[str, Any], only: list[str], size: str
) -> list[Variant]:
    """The Modelly variants (and Mesa's when MESA_PYTHON is set) to run, in registry order.

    ``only`` holds ``playbook`` or ``playbook:variant`` names; empty means all.
    """
    mesa = os.environ.get(MESA_ENV)
    wanted = [item.partition(":") for item in only]
    unknown = [name for name, _, _ in wanted if name not in registry]
    if unknown:
        raise PlaybookError(f"unknown playbook(s): {', '.join(unknown)}")
    chosen = []
    for playbook, spec in registry.items():
        if size not in spec["sizes"]:
            raise PlaybookError(
                f"{playbook} has no size {size!r}: {sorted(spec['sizes'])}"
            )
        for name in spec["variants"]:
            if _wanted(wanted, playbook, name):
                python = mesa if name == MESA_VARIANT and mesa else sys.executable
                if name.startswith(MODELLY_PREFIX) or (name == MESA_VARIANT and mesa):
                    chosen.append(Variant(playbook, name, python))
    return chosen


def _wanted(wanted: list[tuple[str, str, str]], playbook: str, name: str) -> bool:
    """Whether ``--only`` asks for this variant (an empty ``--only`` asks for all)."""
    if not wanted:
        return True
    return any(p == playbook and (not v or v == name) for p, _, v in wanted)


def run_once(directory: Path, variant: Variant, seed: int, size: str) -> dict[str, Any]:
    """Run ``variant`` once in a new interpreter and return its RESULT row."""
    command = [
        variant.python,
        str(directory / WORKER_FILE),
        variant.playbook,
        variant.name,
        str(seed),
        size,
    ]
    done = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", check=False
    )
    for line in done.stdout.splitlines():
        if line.startswith(RESULT_PREFIX):
            result: dict[str, Any] = json.loads(line[len(RESULT_PREFIX) :])
            return result
    raise PlaybookError(
        f"{variant.key} failed (exit {done.returncode}):\n{done.stderr.strip()}"
    )
