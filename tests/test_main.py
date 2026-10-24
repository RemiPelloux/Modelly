"""Tests for ``python -m modelly``: the command list, --version and forwarding."""

import importlib

import pytest

import modelly
from modelly.__main__ import COMMANDS, EXIT_USAGE, main


def test_help_lists_every_command(capsys):
    """--help names each registered command with its summary."""
    with pytest.raises(SystemExit) as stop:
        main(["--help"])
    assert stop.value.code == 0
    out = capsys.readouterr().out
    assert all(name in out and summary in out for name, _, summary in COMMANDS)
    assert "exit status:" in out


def test_version(capsys):
    """--version prints the package version."""
    with pytest.raises(SystemExit):
        main(["--version"])
    assert capsys.readouterr().out.strip() == f"modelly {modelly.__version__}"


def test_forwards_to_the_command(tmp_path, capsys):
    """``modelly lint PATH`` is ``python -m modelly.lint PATH``."""
    path = tmp_path / "model.py"
    path.write_text("import random\nx = random.random()\n")
    assert main(["lint", str(path)]) == 1
    assert "MDL001" in capsys.readouterr().out
    assert main(["lint", "--list-rules"]) == 0


@pytest.mark.parametrize("argv", [[], ["nope"]])
def test_missing_or_unknown_command(argv, capsys):
    """No command or an unknown one is a usage error."""
    with pytest.raises(SystemExit) as stop:
        main(argv)
    assert stop.value.code == EXIT_USAGE
    assert "usage: modelly" in capsys.readouterr().err


def test_every_command_module_has_main():
    """Each registry entry points at a module with a main function."""
    for _, module, _ in COMMANDS:
        assert callable(importlib.import_module(module).main)
