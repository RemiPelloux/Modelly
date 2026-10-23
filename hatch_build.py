"""Hatch build hook: compile modelly._native.fastrng into the wheel when possible.

The extension is optional. Without a C compiler (or with MODELLY_PURE_PYTHON=1)
the wheel is pure Python and ``modelly.FastRandom`` uses its Python fallback;
MODELLY_REQUIRE_NATIVE=1 turns a failed compile into a build error (release
wheels). Editable installs compile the module in place, next to its source.
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

SOURCE = Path("modelly") / "_native" / "fastrng.c"
OPTIMISE = ["-O3", "-fPIC", "-fno-strict-aliasing"]


def compile_extension(root: Path, out_dir: Path) -> Path | None:
    """Compile the C core with the interpreter's own linker command; None on failure."""
    ldshared = sysconfig.get_config_var("LDSHARED")
    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    if not ldshared or not suffix or os.name == "nt":
        return None
    out = out_dir / f"fastrng{suffix}"
    cmd = [
        *shlex.split(ldshared),
        *OPTIMISE,
        f"-I{sysconfig.get_paths()['include']}",
        str(root / SOURCE),
        "-o",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.stderr.write(f"modelly: native core not built:\n{result.stderr}\n")
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
            compile_extension(root, root / SOURCE.parent)
            return
        built = compile_extension(
            root, Path(tempfile.mkdtemp(prefix="modelly-native-"))
        )
        if built is None:
            if os.environ.get("MODELLY_REQUIRE_NATIVE"):
                raise RuntimeError(
                    "MODELLY_REQUIRE_NATIVE is set but the C core did not build"
                )
            return
        build_data["force_include"][str(built)] = f"modelly/_native/{built.name}"
        build_data["pure_python"] = False
        build_data["infer_tag"] = True
