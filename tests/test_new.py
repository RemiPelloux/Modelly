"""Tests for ``modelly new``: every template writes a project that passes its own test and lint."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from modelly.__main__ import main as umbrella
from modelly.lint import lint_paths
from modelly.lint.config import load_config
from modelly.new import TEMPLATES, ProjectError, create_project, placeholders
from modelly.new.__main__ import EXIT_CLEAN, EXIT_USAGE, main

REPO = Path(__file__).resolve().parents[1]
EXPECTED = {
    "pyproject.toml",
    "README.md",
    ".gitignore",
    "tests/test_determinism.py",
    "{package}/__init__.py",
    "{package}/scenario.py",
    "{package}/agents.py",
    "{package}/model.py",
}


def run_pytest(project: Path) -> subprocess.CompletedProcess:
    """Run the generated project's tests in a fresh interpreter that imports this modelly."""
    env = os.environ | {"PYTHONPATH": os.pathsep.join([str(project), str(REPO)])}
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_template_passes_its_test_and_lint(tmp_path, template):
    """The generated project's determinism test passes and modelly lint finds nothing."""
    if template == "network":
        pytest.importorskip("networkx")
    if template == "geo":
        pytest.importorskip("geopandas")
    project = tmp_path / f"demo-{template}"
    written = create_project(project, template)
    names = {path.relative_to(project).as_posix() for path in written}
    assert names == {name.replace("{package}", f"demo_{template}") for name in EXPECTED}
    result = run_pytest(project)
    assert result.returncode == 0, result.stdout + result.stderr
    config = load_config(project)
    assert [f for f in lint_paths([project]) if config.keeps(f)] == []


def test_files_have_no_placeholders_left(tmp_path):
    """Every placeholder is replaced, and the lint table is the documented one."""
    project = tmp_path / "Forest-Fire"
    create_project(project, "grid")
    for path in project.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert "{package}" not in text and "{model_class}" not in text
    pyproject = (project / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "Forest-Fire"' in pyproject and "[tool.modelly.lint]" in pyproject
    assert "modelly-abm>=" in pyproject
    readme = (project / "README.md").read_text(encoding="utf-8")
    assert "ODD" in readme and "ForestFireModel" in readme
    assert not list(project.rglob("*.sh")) and not list(project.rglob("*.ps1"))


def test_names():
    """Project names map to a package and class names; the network template asks for networkx."""
    values = placeholders("my-epidemic.model", "network")
    assert values.package == "my_epidemic_model"
    assert values.model_class == "MyEpidemicModel"
    assert values.scenario_class == "MyEpidemicScenario"
    assert values.requirement.startswith("modelly-abm[network]>=")
    for bad in ("1model", "class", "", "a b"):
        with pytest.raises(ProjectError):
            placeholders(bad, "grid")
    with pytest.raises(ProjectError):
        placeholders("ok", "nope")


def test_refuses_a_non_empty_folder(tmp_path, capsys):
    """An existing file in the folder stops the command before anything is written."""
    (tmp_path / "keep.txt").write_text("mine", encoding="utf-8")
    assert main([str(tmp_path)]) == EXIT_USAGE
    assert "not empty" in capsys.readouterr().err
    assert sorted(p.name for p in tmp_path.iterdir()) == ["keep.txt"]
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main([str(empty), "--template", "cohort"]) == EXIT_CLEAN
    assert (empty / "pyproject.toml").is_file()


def test_cli_list_and_umbrella(tmp_path, capsys):
    """--list-templates prints each template; `modelly new` runs the same command."""
    assert main(["--list-templates"]) == EXIT_CLEAN
    out = capsys.readouterr().out
    assert all(name in out for name in TEMPLATES)
    assert (
        umbrella(["new", str(tmp_path / "x"), "--template", "continuous"]) == EXIT_CLEAN
    )
    assert "python -m pytest" in capsys.readouterr().out
    with pytest.raises(SystemExit) as stop:
        main([])
    assert stop.value.code == EXIT_USAGE


def test_from_zoo_copies_a_zoo_model(tmp_path, capsys):
    """``--from-zoo`` writes the zoo model instead of a template; an unknown name is a usage error."""
    target = tmp_path / "traffic"
    assert main([str(target), "--from-zoo", "nagel_schreckenberg"]) == EXIT_CLEAN
    assert (target / "model.py").is_file()
    assert "wrote" in capsys.readouterr().out
    assert main([str(tmp_path / "other"), "--from-zoo", "no_such_model"]) == EXIT_USAGE
