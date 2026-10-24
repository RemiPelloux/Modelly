"""The two interpreters the performance guard compares (see ``modelly.dev.perf``).

The baseline is the last release, built from its tag in this repository (``git+file``, the
local compiler, no network) into a cached virtual environment with the same numpy, pandas,
scipy and networkx as this interpreter. Both sides are compiled by the same toolchain, so the
only difference is Modelly's source. The candidate is this checkout, run by this interpreter with its compiled modules
built in place.
"""

from __future__ import annotations

import importlib.metadata
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

BENCH_DIR = ".modelly-bench"
PINNED = ("numpy", "pandas", "scipy", "networkx")
TAG_PATTERN = "v[0-9]*"


class PerfEnvError(RuntimeError):
    """The baseline release or this checkout's build could not be prepared."""


def git(root: Path, *args: str) -> str:
    """The stripped output of ``git args`` in ``root``."""
    executable = shutil.which("git")
    if executable is None:
        raise PerfEnvError("git is not on PATH")
    done = subprocess.run(
        [executable, *args], cwd=root, capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise PerfEnvError(done.stderr.strip() or f"git {' '.join(args)} failed")
    return done.stdout.strip()


def baseline_version(root: Path) -> str:
    """The version of the last release tag reachable from HEAD (``v1.3.1`` -> ``1.3.1``)."""
    tag = git(root, "describe", "--tags", "--abbrev=0", "--match", TAG_PATTERN)
    return tag.removeprefix("v")


def venv_python(directory: Path) -> Path:
    """The interpreter of the virtual environment in ``directory``, on any OS."""
    if os.name == "nt":
        return directory / "Scripts" / "python.exe"
    return directory / "bin" / "python"


def pinned_requirements() -> list[str]:
    """``name==version`` for each pinned dependency installed in this interpreter."""
    pins = []
    for name in PINNED:
        try:
            pins.append(f"{name}=={importlib.metadata.version(name)}")
        except importlib.metadata.PackageNotFoundError:
            continue
    return pins


def ensure_baseline(root: Path, version: str) -> Path:
    """The interpreter of the cached baseline environment, created on first use.

    It is built in a ``.partial`` folder and moved into place once the install succeeded, so
    a failed build (a compiler missing, the tag absent) leaves nothing to reuse.
    """
    tag = f"py{sys.version_info.major}{sys.version_info.minor}"
    directory = root / BENCH_DIR / f"baseline-{version}-{tag}"
    if venv_python(directory).exists():
        return venv_python(directory)
    partial = directory.with_name(directory.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    venv.create(partial, with_pip=True)
    command = [
        str(venv_python(partial)),
        "-m",
        "pip",
        "install",
        "--quiet",
        "--disable-pip-version-check",
        release_source(root, version),
        *pinned_requirements(),
    ]
    if subprocess.run(command, check=False).returncode != 0:
        shutil.rmtree(partial, ignore_errors=True)
        raise PerfEnvError(f"could not build modelly-abm {version} from tag v{version}")
    os.replace(partial, directory)
    return venv_python(directory)


def release_source(root: Path, version: str) -> str:
    """The pip requirement that builds release ``version`` from its tag in this repository."""
    return f"modelly-abm @ git+{root.resolve().as_uri()}@v{version}"


def ensure_native(root: Path) -> None:
    """Build this checkout's compiled modules if one is missing or older than its source."""
    sys.path.insert(0, str(root))
    try:
        from hatch_build import NATIVE_DIR, SOURCES, compile_extension  # noqa: PLC0415
    finally:
        sys.path.remove(str(root))
    out_dir = root / NATIVE_DIR
    for source in SOURCES:
        built = sorted(out_dir.glob(f"{source.stem}.*{_suffix()}"))
        if built and built[-1].stat().st_mtime >= _newest_source(root, source):
            continue
        if compile_extension(root, out_dir, source) is None:
            raise PerfEnvError(
                f"{source.name} did not compile: the comparison would be unfair"
            )


def _suffix() -> str:
    """The extension-module suffix's last part (``.so`` or ``.pyd``)."""
    import sysconfig  # noqa: PLC0415

    return Path(sysconfig.get_config_var("EXT_SUFFIX") or ".so").suffix


def _newest_source(root: Path, source: Path) -> float:
    """The newest modification time of ``source`` and the headers next to it."""
    folder = (root / source).parent
    files = [root / source, *folder.glob("*.h")]
    return max(path.stat().st_mtime for path in files)


def candidate_env(root: Path) -> dict[str, str]:
    """The environment that makes this interpreter import this checkout's modelly."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(root), env.get("PYTHONPATH")])
    )
    env.pop("MODELLY_PURE_PYTHON", None)
    return env
