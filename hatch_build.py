"""Hatch build hook: compile the modelly._native C modules into the wheel when possible.

Every module is optional and has a pure-Python fallback with identical results.
Without a C compiler (or with MODELLY_PURE_PYTHON=1) the wheel is pure Python;
MODELLY_REQUIRE_NATIVE=1 turns a failed compile into a build error (release
wheels). Editable installs compile the modules in place, next to their sources.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

try:
    from hatchling.builders.hooks.plugin.interface import BuildHookInterface
except ImportError:  # scripts/build-native.sh only needs compile_extension
    BuildHookInterface = object  # type: ignore[assignment,misc]

NATIVE_DIR = Path("modelly") / "_native"
SOURCES = (
    NATIVE_DIR / "fastrng.c",
    NATIVE_DIR / "fastloop.c",
    NATIVE_DIR / "fastcell.c",
)
OPTIMISE = ["-O3", "-fPIC", "-fno-strict-aliasing"]


def compile_extension(root: Path, out_dir: Path, source: Path) -> Path | None:
    """Compile one C module with the interpreter's own linker command; None on failure."""
    ldshared = sysconfig.get_config_var("LDSHARED")
    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    if not ldshared or not suffix or os.name == "nt":
        return None
    out = out_dir / f"{source.stem}{suffix}"
    cmd = [
        *shlex.split(ldshared),
        *OPTIMISE,
        f"-I{sysconfig.get_paths()['include']}",
        str(root / source),
        "-o",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(f"modelly: {source.name} not built:\n{result.stderr}\n")
        return None
    return out


class CustomBuildHook(BuildHookInterface):
    """Add the compiled core to platform wheels."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict) -> None:
        """Compile before the wheel is assembled."""
        if self.target_name != "wheel" or os.environ.get("MODELLY_PURE_PYTHON"):
            return
        root = Path(self.root)
        if version == "editable":
            for source in SOURCES:
                compile_extension(root, root / NATIVE_DIR, source)
            return
        out_dir = Path(tempfile.mkdtemp(prefix="modelly-native-"))
        built = [compile_extension(root, out_dir, source) for source in SOURCES]
        if None in built and os.environ.get("MODELLY_REQUIRE_NATIVE"):
            raise RuntimeError(
                "MODELLY_REQUIRE_NATIVE is set but a C module did not build"
            )
        for path in filter(None, built):
            build_data["force_include"][str(path)] = f"modelly/_native/{path.name}"
            build_data["pure_python"] = False
            build_data["infer_tag"] = True
