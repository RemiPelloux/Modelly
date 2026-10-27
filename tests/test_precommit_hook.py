"""Tests for the pre-commit hooks in ``.pre-commit-hooks.yaml``: their entries lint staged files."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parents[1]
HOOKS = REPO / ".pre-commit-hooks.yaml"
BAD = "import random\nfrom modelly import Agent\nclass A(Agent):\n    def step(self):\n        x = random.random()\n"
GOOD = "x = 1\n"
VCS = shutil.which("git")


def vcs(root: Path, *args: str) -> str:
    """Run git in ``root`` and return its output; skip the test without git."""
    if VCS is None:
        pytest.skip("git is not installed")
    done = subprocess.run(
        [VCS, *args], cwd=root, capture_output=True, text=True, check=True
    )
    return done.stdout


def hooks() -> dict[str, dict]:
    """The hooks by id."""
    return {
        hook["id"]: hook for hook in yaml.safe_load(HOOKS.read_text(encoding="utf-8"))
    }


def staged_python_files(root: Path) -> list[str]:
    """What pre-commit passes a ``types: [python]`` hook: the staged ``.py`` files."""
    names = vcs(root, "diff", "--cached", "--name-only", "--diff-filter=ACM").split()
    return [name for name in names if name.endswith(".py")]


def run_hook(hook: dict, root: Path) -> subprocess.CompletedProcess:
    """Run ``hook``'s entry on the staged files, as pre-commit would (``modelly`` -> this one)."""
    program, *args = hook["entry"].split()
    assert program == "modelly"
    env = os.environ | {"PYTHONPATH": str(REPO)}
    return subprocess.run(
        [sys.executable, "-m", "modelly", *args, *staged_python_files(root)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def staged(tmp_path: Path) -> Path:
    """A git repository with a bad and a clean model staged and an unstaged bad one."""
    vcs(tmp_path, "init", "-q")
    (tmp_path / "bad.py").write_text(BAD, encoding="utf-8")
    (tmp_path / "good.py").write_text(GOOD, encoding="utf-8")
    (tmp_path / "notes.txt").write_text("random.random()\n", encoding="utf-8")
    vcs(tmp_path, "add", "bad.py", "good.py", "notes.txt")
    (tmp_path / "unstaged.py").write_text(BAD, encoding="utf-8")
    return tmp_path


def test_hook_definitions():
    """Both hooks run ``modelly lint`` on Python files, once with every file."""
    found = hooks()
    assert set(found) == {"modelly-lint", "modelly-lint-fix"}
    for hook in found.values():
        assert hook["entry"].startswith("modelly lint")
        assert hook["language"] == "python" and hook["types"] == ["python"]
        assert hook["require_serial"] is True
    assert found["modelly-lint-fix"]["entry"].endswith("--fix")


def test_lint_hook_fails_on_a_staged_finding(staged):
    """The staged bad file fails the hook; unstaged and non-Python files are not read."""
    result = run_hook(hooks()["modelly-lint"], staged)
    assert result.returncode == 1, result.stderr
    assert "bad.py:5:13: MDL001" in result.stdout
    assert "unstaged.py" not in result.stdout and "good.py" not in result.stdout


def test_fix_hook_rewrites_the_staged_file(staged):
    """The fix hook applies the safe fix, so nothing is left to report."""
    result = run_hook(hooks()["modelly-lint-fix"], staged)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "self.random.random()" in (staged / "bad.py").read_text(encoding="utf-8")
    assert (staged / "unstaged.py").read_text(encoding="utf-8") == BAD


def test_lint_hook_passes_clean_files(staged):
    """With only the clean file staged the hook passes."""
    vcs(staged, "rm", "-q", "--cached", "bad.py")
    assert run_hook(hooks()["modelly-lint"], staged).returncode == 0
