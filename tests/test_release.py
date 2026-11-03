"""scripts/release.py, rehearsed in a temporary git repository (never this checkout)."""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release.py"
GIT = shutil.which("git")
DATE = "2031-02-03"
VERSION = "9.8.7"
EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2

pytestmark = pytest.mark.skipif(GIT is None, reason="needs git")


def _load():
    spec = importlib.util.spec_from_file_location("release", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # Before Python 3.15, @dataclass looks its module up in sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


release = _load()

FILES = {
    "modelly/__init__.py": '"""Modelly."""\n\n__version__ = "1.2.0"\n',
    "CITATION.cff": 'cff-version: "1.2.0"\nversion: "1.2.0"\ndate-released: "2026-10-24"\n',
    "CHANGELOG.md": "# Changelog\n\nIntro.\n\n## 1.2.0 - 2026-10-24\n\n- Old.\n",
    "docs/whats_new.md": "# What's new\n\n## Unreleased\n\n- Shiny.\n\n## 1.2.0 - 2026-10-24\n",
}


def _git(repo, *args):
    return subprocess.run(
        [GIT, *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A repository on main with the four files a release changes, committed."""
    path = tmp_path / "repo"
    for name, text in FILES.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text, encoding="utf-8", newline="\n")
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "release@example.invalid")
    _git(path, "config", "user.name", "Release Test")
    _git(path, "config", "commit.gpgsign", "false")
    _git(path, "config", "tag.gpgsign", "false")
    _git(path, "add", "--", *FILES)
    _git(path, "commit", "-q", "-m", "chore: start")
    return path


def _cut(repo, *extra):
    return release.main(
        [VERSION, "--root", str(repo), "--date", DATE, "--no-gate", *extra]
    )


def test_dry_run_is_the_default_and_changes_nothing(repo, capsys):
    """Without --apply the plan is printed and the repository is untouched."""
    assert _cut(repo) == EXIT_OK
    out = capsys.readouterr().out
    assert "would update CHANGELOG.md" in out and "dry run" in out
    assert _git(repo, "status", "--porcelain") == ""
    assert _git(repo, "tag") == ""


def test_apply_bumps_commits_and_tags(repo):
    """--apply writes the four files, one trailer-free commit and the tag."""
    assert _cut(repo, "--apply") == EXIT_OK
    assert f'__version__ = "{VERSION}"' in (repo / "modelly/__init__.py").read_text(
        encoding="utf-8"
    )
    citation = (repo / "CITATION.cff").read_text(encoding="utf-8")
    assert (
        f'version: "{VERSION}"' in citation and f'date-released: "{DATE}"' in citation
    )
    assert 'cff-version: "1.2.0"' in citation
    changelog = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"Intro.\n\n## {VERSION} - {DATE}\n\n## 1.2.0" in changelog
    whats_new = (repo / "docs/whats_new.md").read_text(encoding="utf-8")
    assert (
        f"## {VERSION} - {DATE}\n\n- Shiny." in whats_new
        and "Unreleased" not in whats_new
    )
    assert _git(repo, "log", "-1", "--format=%B") == f"chore(release): {VERSION}"
    assert _git(repo, "tag") == f"v{VERSION}"
    assert _git(repo, "status", "--porcelain") == ""


def test_unreleased_heading_is_renamed(repo):
    """An existing Unreleased section becomes the release section."""
    changelog = repo / "CHANGELOG.md"
    changelog.write_text(
        FILES["CHANGELOG.md"].replace(
            "## 1.2.0", "## Unreleased\n\n- New.\n\n## 1.2.0"
        ),
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "docs: unreleased")
    assert _cut(repo, "--apply") == EXIT_OK
    text = changelog.read_text(encoding="utf-8")
    assert f"## {VERSION} - {DATE}\n\n- New." in text and "Unreleased" not in text


@pytest.mark.parametrize(
    ("page", "message"),
    [
        ("# What's new\n\n## 1.2.0 - 2026-10-24\n", "no '## Unreleased' section"),
        ("# What's new\n\n## Unreleased\n\n\n## 1.2.0 - 2026-10-24\n", "are empty"),
    ],
)
def test_no_release_without_its_notes(repo, capsys, page, message):
    """A What's new page with no Unreleased notes, or empty ones, stops the release."""
    (repo / "docs/whats_new.md").write_text(page, encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "docs: no notes")
    assert _cut(repo, "--apply") == EXIT_FAILED
    assert message in capsys.readouterr().err
    assert _git(repo, "tag") == ""


def test_push_sends_main_and_the_tag(repo, tmp_path):
    """--push pushes the release commit and its tag to origin."""
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    assert _cut(repo, "--apply", "--push") == EXIT_OK
    assert _git(remote, "tag") == f"v{VERSION}"
    assert (
        _git(remote, "log", "-1", "--format=%s", "main") == f"chore(release): {VERSION}"
    )


def test_refusals(repo, capsys):
    """A dirty tree, another branch, an existing tag or bad arguments stop the release."""
    (repo / "CHANGELOG.md").write_text("dirty", encoding="utf-8")
    assert _cut(repo) == EXIT_FAILED
    _git(repo, "checkout", "-q", "--", "CHANGELOG.md")
    _git(repo, "checkout", "-q", "-b", "feature")
    assert _cut(repo) == EXIT_FAILED
    _git(repo, "checkout", "-q", "main")
    _git(repo, "tag", f"v{VERSION}")
    assert _cut(repo) == EXIT_FAILED
    err = capsys.readouterr().err
    assert "uncommitted" in err and "not feature" in err and "already exists" in err
    assert release.main(["1.3", "--root", str(repo)]) == EXIT_USAGE
    assert release.main([VERSION, "--push", "--root", str(repo)]) == EXIT_USAGE


def test_gate_runs_before_anything_is_written(repo, monkeypatch):
    """Without --no-gate the gate runs first, and its failure stops the release."""

    def failing_gate(_release):
        raise release.ReleaseError("the gate failed")

    monkeypatch.setattr(release, "run_gate", failing_gate)
    assert release.main([VERSION, "--root", str(repo), "--apply"]) == EXIT_FAILED
    assert _git(repo, "tag") == ""


def test_changelog_edits_are_refused_when_impossible():
    """A version already in the changelog, or no heading at all, is an error."""
    with pytest.raises(release.ReleaseError, match="already has"):
        release.bumped_changelog("## 9.8.7 - x\n", VERSION, DATE)
    with pytest.raises(release.ReleaseError, match="no release heading"):
        release.bumped_changelog("# Changelog\n", VERSION, DATE)
    with pytest.raises(release.ReleaseError, match="__version__"):
        release.bumped_init("nothing", VERSION)


def test_a_pre_release_records_the_changelog_and_keeps_the_notes(repo):
    """1.3.0rc1 gets its changelog heading; What's new stays Unreleased for the final."""
    assert release.main(["1.3.0rc1", "--root", str(repo), "--date", DATE, "--no-gate",
                         "--apply"]) == EXIT_OK  # fmt: skip
    assert "## 1.3.0rc1 - " in (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    whats_new = (repo / "docs/whats_new.md").read_text(encoding="utf-8")
    assert whats_new == FILES["docs/whats_new.md"]
    assert _git(repo, "tag") == "v1.3.0rc1"
    assert _git(repo, "show", "--name-only", "--format=", "HEAD").split() == [
        "CHANGELOG.md", "CITATION.cff", "modelly/__init__.py",
    ]  # fmt: skip
    assert release.main(["1.3.0c1", "--root", str(repo)]) == EXIT_USAGE


def test_a_gate_passed_on_this_commit_is_not_run_again(repo, monkeypatch, capsys):
    """ci-local.sh's stamp of HEAD skips the gate; a stamp of another commit does not."""
    calls, real = [], release.subprocess.run

    def fake(command, *args, **kwargs):
        if command[0] == release.GIT:
            return real(command, *args, **kwargs)
        calls.append(command)
        return type("Done", (), {"returncode": 1})()

    monkeypatch.setattr(release.subprocess, "run", fake)
    stamp = repo / ".git" / release.GATE_STAMP
    stamp.write_text(_git(repo, "rev-parse", "HEAD") + "\n", encoding="utf-8")
    assert release.main([VERSION, "--root", str(repo), "--date", DATE]) == EXIT_OK
    assert "already passed on this commit" in capsys.readouterr().out and not calls
    stamp.write_text("0" * 40, encoding="utf-8")
    assert release.main([VERSION, "--root", str(repo), "--date", DATE]) == EXIT_FAILED
    assert calls
