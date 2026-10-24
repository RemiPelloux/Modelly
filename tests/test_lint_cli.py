"""Tests for the modelly.lint command line: configuration, output formats and --explain."""

import textwrap
from pathlib import Path

import pytest

from modelly.lint import RULES, lint_source
from modelly.lint.__main__ import EXIT_CLEAN, EXIT_FINDINGS, EXIT_USAGE, main
from modelly.lint.config import ConfigError, load_config
from modelly.lint.explain import EXPLANATIONS
from modelly.lint.report import PROPERTY_ESCAPES, escape

TWO_RULES = "import random\nx = random.random()\nfor a in set(b):\n    pass\n"
DOCS = Path(__file__).parents[1] / "docs" / "lint.md"


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A folder with a model file, used as the working directory."""
    (tmp_path / "model.py").write_text(TWO_RULES)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def configure(project: Path, table: str) -> None:
    """Write a pyproject.toml with ``table`` under [tool.modelly.lint]."""
    body = "[tool.modelly.lint]\n" + textwrap.dedent(table)
    (project / "pyproject.toml").write_text(body)


def test_noqa_allows_a_comment_after_the_codes():
    """``# noqa: MDL001 set-up only`` still names MDL001."""
    assert (
        lint_source("import random\nx = random.random()  # noqa: MDL001 set-up") == []
    )


def test_config_select_and_ignore(project, capsys):
    """Select and ignore in pyproject.toml filter the findings."""
    configure(project, 'ignore = ["MDL001"]\n')
    assert main(["model.py"]) == EXIT_FINDINGS
    out = capsys.readouterr().out
    assert "MDL003" in out and "MDL001" not in out
    configure(project, 'select = ["MDL001"]\n')
    main(["model.py"])
    out = capsys.readouterr().out
    assert "MDL001" in out and "MDL003" not in out


def test_config_per_file_ignores(project):
    """A glob on the relative path or the file name drops codes for that file."""
    configure(project, 'per-file-ignores = { "model.py" = ["MDL0"] }\n')
    assert main(["model.py"]) == EXIT_CLEAN
    (project / "sub").mkdir()
    (project / "sub" / "agents.py").write_text(TWO_RULES)
    configure(project, 'per-file-ignores = { "sub/*" = ["MDL001", "MDL003"] }\n')
    assert main(["sub"]) == EXIT_CLEAN
    assert main(["model.py"]) == EXIT_FINDINGS


def test_cli_flags_replace_the_config(project):
    """--ignore on the command line wins over the file's ignore."""
    configure(project, 'ignore = ["MDL0"]\n')
    assert main(["model.py"]) == EXIT_CLEAN
    assert main(["model.py", "--ignore", "MDL101"]) == EXIT_FINDINGS


def test_bad_config_is_a_usage_error(project, capsys):
    """An unknown key or invalid TOML exits 2 with a message."""
    configure(project, 'per_file_ignores = { "x" = ["MDL0"] }\n')
    with pytest.raises(ConfigError):
        load_config()
    assert main(["model.py"]) == EXIT_USAGE
    (project / "pyproject.toml").write_text("[tool.modelly.lint\n")
    assert main(["model.py"]) == EXIT_USAGE
    assert "modelly.lint" in capsys.readouterr().err


def test_no_pyproject_means_no_filter(tmp_path):
    """Without a pyproject.toml every finding is kept."""
    config = load_config(tmp_path)
    assert config.select == config.ignore == config.per_file_ignores == ()


def test_quiet_prints_only_locations(project, capsys):
    """--quiet drops the hints and the summary line."""
    main(["model.py", "--quiet"])
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "model.py:2:5: MDL001 " + RULES["MDL001"].message,
        "model.py:3:1: MDL003 " + RULES["MDL003"].message,
    ]


def test_statistics_counts_per_code(project, capsys):
    """--statistics prints one count per code and the summary."""
    (project / "other.py").write_text(TWO_RULES)
    main(["--statistics", "."])
    out = capsys.readouterr().out.splitlines()
    assert out[0].split()[:2] == ["2", "MDL001"]
    assert out[-1] == "4 finding(s): 4 error(s), 0 warning(s)"


def test_github_annotations(project, capsys):
    """--format github prints workflow commands with escaped properties."""
    main(["model.py", "--format", "github"])
    first = capsys.readouterr().out.splitlines()[0]
    assert first.startswith("::error file=model.py,line=2,col=5,title=MDL001::")
    assert escape("a,b:c%", PROPERTY_ESCAPES) == "a%2Cb%3Ac%25"


def test_explain_every_rule(capsys):
    """Every rule has a long form with a bad and a good example."""
    assert set(EXPLANATIONS) == set(RULES)
    for code in RULES:
        assert main(["--explain", code.lower()]) == EXIT_CLEAN
        out = capsys.readouterr().out
        assert out.startswith(code) and "Bad:" in out and "Good:" in out


def test_explain_unknown_rule(capsys):
    """An unknown code is a usage error."""
    assert main(["--explain", "MDL999"]) == EXIT_USAGE
    assert "unknown rule" in capsys.readouterr().err


def test_help_documents_examples_and_exit_codes(capsys):
    """--help shows examples, configuration and exit status."""
    with pytest.raises(SystemExit) as stop:
        main(["--help"])
    assert stop.value.code == 0
    out = capsys.readouterr().out
    assert "examples:" in out and "exit status:" in out and "[tool.modelly.lint]" in out


def test_docs_cover_every_rule():
    """docs/lint.md has a section for each rule."""
    text = DOCS.read_text(encoding="utf-8")
    assert all(f"### {code}" in text for code in RULES)
