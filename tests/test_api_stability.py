"""Every public name has a stability level in docs/api_stability.toml.

A new public name fails this test until it is recorded; names new in a minor release
are provisional (``python tools/api/list_public.py --add-new``).
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "api" / "list_public.py"
EXIT_OK, EXIT_MISSING = 0, 1


def _load():
    spec = importlib.util.spec_from_file_location("list_public", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


list_public = _load()


@pytest.fixture(scope="module")
def names():
    """The public names of modelly, as the script finds them."""
    found, failed = list_public.public_names()
    assert failed == [], f"could not import {failed}"
    return found


def test_every_public_name_has_a_level(names):
    """No public name is missing from docs/api_stability.toml."""
    levels = list_public.read_levels()
    missing = [name for name in names if name not in levels]
    assert missing == [], (
        "run: python tools/api/list_public.py --add-new\n" + "\n".join(missing)
    )


def test_no_stale_entries(names):
    """Every recorded name still exists, so a removal is a visible edit of the file."""
    assert sorted(set(list_public.read_levels()) - set(names)) == []


def test_file_is_in_written_form(tmp_path):
    """The file is what write_levels produces: sorted lists, LF line endings."""
    levels = list_public.read_levels()
    copy = tmp_path / "copy.toml"
    list_public.write_levels(levels, copy)
    assert copy.read_bytes() == list_public.STABILITY.read_bytes()


def test_public_means_no_underscore_and_not_an_example():
    """Private modules and the bundled examples are not API."""
    assert list_public._public("modelly.core.model")
    assert not list_public._public("modelly._native.sets")
    assert not list_public._public("modelly.examples.basic")


def test_cli_missing_and_add_new(monkeypatch, tmp_path, capsys):
    """--missing exits 1 while a name is unrecorded; --add-new records it provisional."""
    path = tmp_path / "stability.toml"
    list_public.write_levels({"modelly.Model": "stable"}, path)
    monkeypatch.setattr(list_public, "STABILITY", path)
    monkeypatch.setattr(list_public, "read_levels", lambda: _read(path))
    monkeypatch.setattr(
        list_public, "write_levels", lambda levels: _write(levels, path)
    )
    monkeypatch.setattr(
        list_public,
        "public_names",
        lambda: (["modelly.Model", "modelly.new_thing"], []),
    )
    assert list_public.main(["--missing"]) == EXIT_MISSING
    assert "modelly.new_thing\tMISSING" in capsys.readouterr().out
    assert list_public.main(["--add-new"]) == EXIT_OK
    assert _read(path)["modelly.new_thing"] == "provisional"
    assert list_public.main(["--missing"]) == EXIT_OK
    assert list_public.main([]) == EXIT_OK
    assert "modelly.Model\tstable" in capsys.readouterr().out


_original_read = list_public.read_levels
_original_write = list_public.write_levels


def _read(path):
    return _original_read(path)


def _write(levels, path):
    _original_write(levels, path)
