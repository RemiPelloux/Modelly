"""Tests for ``python -m modelly.netlogo``: output, the report and the exit status."""

from modelly.netlogo.__main__ import EXIT_CLEAN, EXIT_UNTRANSLATED, EXIT_USAGE, main


def test_translates_a_file_to_a_file(tmp_path, capsys):
    """A clean model exits 0 and writes the module; display lines are reported."""
    out = tmp_path / "wolf_sheep.py"
    assert main(["--example", "wolf_sheep", "-o", str(out)]) == EXIT_CLEAN
    assert "class WolfSheepModel(NetLogoModel):" in out.read_text(encoding="utf-8")
    err = capsys.readouterr().err
    assert "wolf_sheep.nlogo:25: display only, dropped" in err


def test_untranslated_lines_exit_1_and_are_listed(tmp_path, capsys):
    """A line outside the subset is on stderr with its line number; exit 1."""
    model = tmp_path / "demo.nlogo"
    model.write_text("to setup\n  layout-circle turtles 5\nend\n", encoding="utf-8")
    assert main([str(model), "--name", "spiral"]) == EXIT_UNTRANSLATED
    captured = capsys.readouterr()
    assert "class SpiralModel(NetLogoModel):" in captured.out
    assert f"{model}:2: not translated: unknown command 'layout-circle'" in captured.err


def test_show_and_usage_errors(tmp_path, capsys):
    """--show prints the bundled source; no input or a missing file exits 2."""
    assert main(["--example", "fire", "--show"]) == EXIT_CLEAN
    assert "to go" in capsys.readouterr().out
    assert main([]) == EXIT_USAGE
    assert main([str(tmp_path / "missing.nlogo")]) == EXIT_USAGE
    assert "modelly netlogo:" in capsys.readouterr().err
