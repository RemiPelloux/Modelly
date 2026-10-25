"""Where and with what a playbook was timed, recorded next to its results."""

from __future__ import annotations

import datetime
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

PACKAGES = ("modelly-abm", "mesa", "mesa-frames", "numpy", "polars", "pandas", "scipy")
VERSIONS = """
import importlib.metadata as m, json, platform
found = {}
for name in PACKAGES:
    try:
        found[name] = m.version(name)
    except m.PackageNotFoundError:
        pass
print(json.dumps({"python": platform.python_version(), "packages": found}))
"""


def read(path: str) -> str:
    """A sysfs or procfs value, or an empty string where the platform has none."""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def cpu(core: int | None) -> dict:
    """The processor and, for the pinned core, its maximum frequency and power policy."""
    model = next(
        (line.split(":", 1)[1].strip() for line in read("/proc/cpuinfo").splitlines()
         if line.startswith("model name")),
        platform.processor(),
    )  # fmt: skip
    info = {"model": model, "cores": os.cpu_count(), "pinned_core": core}
    if core is not None:
        base = f"/sys/devices/system/cpu/cpu{core}/cpufreq/"
        info |= {
            "max_khz": read(base + "cpuinfo_max_freq"),
            "governor": read(base + "scaling_governor"),
            "energy_preference": read(base + "energy_performance_preference"),
            "no_turbo": read("/sys/devices/system/cpu/intel_pstate/no_turbo"),
        }
    return info


def interpreters(pythons: dict[str, str]) -> dict:
    """Python and package versions of every interpreter the variants run in."""
    code = f"PACKAGES = {PACKAGES!r}\n" + VERSIONS
    found = {}
    for label, python in pythons.items():
        out = subprocess.run(
            [python, "-c", code], capture_output=True, text=True, check=False
        )
        lines = out.stdout.strip().splitlines()
        found[label] = json.loads(lines[-1]) if lines else None
    return found


def environment(root: Path, pythons: dict[str, str], core: int | None) -> dict:
    """Commit, time, machine, load and versions at the start of a playbook's timing."""
    git = shutil.which("git") or "git"
    commit = subprocess.run(
        [git, "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            [git, "status", "--porcelain", "--", "modelly", "benchmarks/playbooks"],
            cwd=root, capture_output=True, text=True, check=False,
        ).stdout.strip()
    )  # fmt: skip
    return {
        "date": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "commit": commit,
        "uncommitted_changes": dirty,
        "load_average": os.getloadavg() if hasattr(os, "getloadavg") else None,
        "cpu": cpu(core),
        "interpreters": interpreters(pythons),
    }
