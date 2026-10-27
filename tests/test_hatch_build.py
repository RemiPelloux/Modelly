"""Tests for the build hook's compile commands, native and WebAssembly."""

from pathlib import Path

from hatch_build import OPTIMISE, build_commands

SOURCE = Path("modelly/_native/fastrng.c")


def test_native_build_is_one_command():
    """A host build compiles and links in one call of LDSHARED."""
    out = Path("out/fastrng.cpython-314-x86_64-linux-gnu.so")
    (command,) = build_commands("cc -shared", SOURCE, out)
    assert command[:2] == ["cc", "-shared"]
    assert command[-3:] == [str(SOURCE), "-o", str(out)]
    assert all(flag in command for flag in OPTIMISE)


def test_webassembly_build_compiles_then_links():
    """With pyodide build: an object file first, then a -shared link of it."""
    out = Path("out/fastrng.cpython-314-wasm32-emscripten.so")
    compile_step, link_step = build_commands("cc", SOURCE, out)
    obj = str(out.with_suffix(".o"))
    assert compile_step[-4:] == ["-c", str(SOURCE), "-o", obj]
    assert link_step == ["cc", "-shared", obj, "-o", str(out)]
