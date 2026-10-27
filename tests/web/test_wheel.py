"""Tests for the pure-Python Modelly wheel a browser site ships."""

import subprocess
import sys
import zipfile
from pathlib import PurePosixPath

import modelly
from modelly.web.wheel import package_files, wheel_name, write_wheel

SCHELLING = PurePosixPath("examples/basic/schelling")


def test_files_leave_out_compiled_sources_and_desktop_tools():
    """No C source, compiled module, viz, examples or command-line tools."""
    files = package_files()
    names = {str(path) for path in files}
    assert "web/runtime.py" in names
    assert "web/site/worker.js" in names
    assert "studio/params.py" in names
    assert not any(p.suffix in {".c", ".h", ".so", ".pyc"} for p in files)
    assert not any(p.parts[0] in {"viz", "examples", "dev", "bench"} for p in files)
    assert files == sorted(files)


def test_keep_an_example_and_the_packages_above_it():
    """An exported example keeps its folder and the __init__ files that reach it."""
    names = {str(path) for path in package_files(SCHELLING)}
    assert "examples/basic/schelling/model.py" in names
    assert "examples/basic/schelling/resources/blue_happy.png" in names
    assert {"examples/__init__.py", "examples/basic/__init__.py"} <= names
    assert "examples/basic/boid_flockers/model.py" not in names
    assert "examples/advanced/__init__.py" not in names


def test_wheel_is_deterministic_and_recorded(tmp_path):
    """Two builds give the same bytes; RECORD lists every file and the metadata."""
    first = write_wheel(tmp_path / "a")
    second = write_wheel(tmp_path / "b")
    assert (
        first.name
        == wheel_name()
        == f"modelly_abm-{modelly.__version__}-py3-none-any.whl"
    )
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        names = archive.namelist()
        info = f"modelly_abm-{modelly.__version__}.dist-info"
        record = archive.read(f"{info}/RECORD").decode().splitlines()
        metadata = archive.read(f"{info}/METADATA").decode()
    assert f"Version: {modelly.__version__}" in metadata
    assert {line.split(",")[0] for line in record} == set(names)


def test_wheel_imports_without_compiled_modules(tmp_path):
    """Unpacked on its own, the wheel imports Modelly and the browser runtime."""
    with zipfile.ZipFile(write_wheel(tmp_path)) as archive:
        archive.extractall(tmp_path / "site")
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import modelly, modelly.web.runtime;"
        "from modelly.web.runtime import native_modules;"
        "assert modelly.__file__.startswith(sys.argv[1]), modelly.__file__;"
        "assert native_modules() == []"
    )
    command = [sys.executable, "-c", code, str(tmp_path / "site")]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
