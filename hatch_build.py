"""Hatch build hook: compile the modelly._native C modules into the wheel when possible.

Every module is optional and has a pure-Python fallback with identical results.
Without a C compiler (or with MODELLY_PURE_PYTHON=1) the wheel is pure Python;
MODELLY_REQUIRE_NATIVE=1 turns a failed compile into a build error (release
wheels). Editable installs compile the modules in place, next to their sources.
On Windows the modules are compiled by setuptools' build_ext, which finds MSVC
and links against the interpreter's import library.
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
    NATIVE_DIR / "fastset.c",
    NATIVE_DIR / "fastevents.c",
)
OPTIMISE = ["-O3", "-fPIC", "-fno-strict-aliasing"]
# In the EXT_SUFFIX of a WebAssembly build (cpython-314-wasm32-emscripten.so).
EMSCRIPTEN = "emscripten"


def compile_with_setuptools(root: Path, out_dir: Path, source: Path) -> Path | None:
    """Compile one C module with setuptools' build_ext (MSVC on Windows); None on failure."""
    try:
        from setuptools import Distribution, Extension  # noqa: PLC0415 - Windows only
        from setuptools.command.build_ext import build_ext  # noqa: PLC0415
        from setuptools.errors import BaseError, CCompilerError  # noqa: PLC0415
    except ImportError:
        sys.stderr.write("modelly: setuptools is needed to compile on Windows\n")
        return None
    extension = Extension(source.stem, [str(root / source)])
    command = build_ext(Distribution({"ext_modules": [extension]}))
    command.build_lib = str(out_dir)
    command.build_temp = tempfile.mkdtemp(prefix="modelly-obj-")
    try:
        command.ensure_finalized()
        command.run()
    # No MSVC found (BaseError), a compile or link error (CCompilerError), a file error.
    except (BaseError, CCompilerError, OSError) as error:
        sys.stderr.write(f"modelly: {source.name} not built:\n{error}\n")
        return None
    return Path(command.get_ext_fullpath(source.stem))


def build_commands(ldshared: str, source: Path, out: Path) -> list[list[str]]:
    """The commands that compile ``source`` into the extension module ``out``.

    One compile-and-link command, except for WebAssembly (``pyodide build``, whose
    EXT_SUFFIX names emscripten): its compiler wrapper adds the cross-compiled Python
    headers to ``-c`` commands only and reads the exports from object files, so the
    module is compiled to an object first and then linked with ``-shared``.
    """
    compiler = [
        *shlex.split(ldshared),
        *OPTIMISE,
        f"-I{sysconfig.get_paths()['include']}",
    ]
    if EMSCRIPTEN not in out.name:
        return [[*compiler, str(source), "-o", str(out)]]
    obj = out.with_suffix(".o")
    return [
        [*compiler, "-c", str(source), "-o", str(obj)],
        [*shlex.split(ldshared), "-shared", str(obj), "-o", str(out)],
    ]


def compile_extension(root: Path, out_dir: Path, source: Path) -> Path | None:
    """Compile one C module with the interpreter's linker (setuptools on Windows); None on failure."""
    if os.name == "nt":
        return compile_with_setuptools(root, out_dir, source)
    ldshared = sysconfig.get_config_var("LDSHARED")
    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    if not ldshared or not suffix:
        return None
    out = out_dir / f"{source.stem}{suffix}"
    for cmd in build_commands(ldshared, root / source, out):
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
