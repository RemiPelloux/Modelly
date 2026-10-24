"""The performance guard: its verdict, the hook's file filter and setup, the baseline."""

import io
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from modelly.dev import hooks, perf, perf_env
from modelly.dev.__main__ import main

ROOT = Path(__file__).resolve().parents[1]
THRESHOLD = 1.03


def timing(ratio, low, high=None):
    """A Timing with the given median ratio and quartiles."""
    return perf.Timing("op", 100.0, 100.0 * ratio, ratio, low, high or ratio)


def test_slower_needs_the_median_and_the_low_quartile():
    """A regression: median above the threshold and even the fast quarter slower."""
    assert timing(1.10, 1.05).slower(THRESHOLD)
    assert not timing(1.10, 0.99).slower(THRESHOLD)  # noisy: some bursts were faster
    assert not timing(1.02, 1.01).slower(THRESHOLD)  # within the threshold
    assert not timing(0.90, 0.85).slower(THRESHOLD)


def test_report_names_the_slower_operations():
    """The verdict line lists the regressions, or says there are none."""
    slow = perf.Timing("column read", 50.0, 60.0, 1.2, 1.15, 1.25)
    fine = perf.Timing("agentset do", 40.0, 39.0, 0.98, 0.95, 1.01)
    text = perf.report([slow, fine], "1.3.1", THRESHOLD)
    assert "column read" in text.splitlines()[1] and "SLOWER" in text.splitlines()[1]
    assert text.splitlines()[-1] == "slower than 1.3.1: column read"
    assert perf.report([fine], "1.3.1", THRESHOLD).endswith(
        "no operation slower than 1.3.1 (threshold 1.03)"
    )


def test_a_suspect_is_timed_again_and_that_result_counts(monkeypatch):
    """One noisy session cannot refuse a commit: the confirmation session decides."""
    calls = []

    def session(release, root, env, pairs, names=None, *, swap=False):
        calls.append((names, pairs, swap))
        if names is None:
            return {"a": timing(1.2, 1.1), "b": timing(1.0, 0.98)}
        return {"a": timing(1.0, 0.97)}

    monkeypatch.setattr(perf, "_session", session)
    result = {t.name: t for t in perf.compare(Path("py"), ROOT, {}, 8, THRESHOLD)}
    assert calls == [(None, 8, False), (["a"], 8 * perf.CONFIRM_FACTOR, True)]
    assert not any(t.slower(THRESHOLD) for t in result.values())


def test_staged_code_keeps_modelly_sources_only(monkeypatch):
    """Docs, tests and benchmarks do not trigger the guard; modelly's .py, .c and .h do."""
    staged = "docs/index.md\ntests/test_x.py\nmodelly/core/agent.py\nmodelly/_native/fastcell.c\nmodelly/x.txt"
    monkeypatch.setattr(hooks, "git", lambda root, *args: staged)
    assert hooks.staged_code(ROOT) == [
        "modelly/core/agent.py",
        "modelly/_native/fastcell.c",
    ]


def test_staged_run_without_code_changes_passes_at_once(monkeypatch):
    """A docs-only commit is not timed at all."""
    monkeypatch.setattr(hooks, "staged_code", lambda root: [])
    out = io.StringIO()
    assert hooks.run_perf(ROOT, out, staged=True, against=None) == hooks.EXIT_PASSED
    assert out.getvalue() == ""


def test_skip_variable_skips(monkeypatch):
    """MODELLY_SKIP_PERF=1 skips the guard and says so."""
    monkeypatch.setenv(hooks.SKIP_ENV, "1")
    out = io.StringIO()
    assert hooks.run_perf(ROOT, out, staged=False, against="1.3.1") == hooks.EXIT_PASSED
    assert "skipped" in out.getvalue()


def test_a_failed_baseline_is_a_usage_error(monkeypatch):
    """No baseline (no tag, no compiler): exit 2 with the reason, never a silent pass."""

    def broken(root, version):
        raise perf_env.PerfEnvError("could not build modelly-abm 9.9.9 from tag v9.9.9")

    monkeypatch.setattr(hooks, "ensure_baseline", broken)
    out = io.StringIO()
    assert hooks.run_perf(ROOT, out, staged=False, against="9.9.9") == hooks.EXIT_USAGE
    assert "tag v9.9.9" in out.getvalue()


def test_release_source_builds_the_tag_from_this_repository(tmp_path):
    """The baseline is built from the tag in the local repository, not downloaded."""
    source = perf_env.release_source(tmp_path, "1.3.1")
    assert source.startswith("modelly-abm @ git+file:") and source.endswith("@v1.3.1")


def test_venv_python_on_each_platform(monkeypatch, tmp_path):
    """bin/python on POSIX, Scripts/python.exe on Windows."""
    monkeypatch.setattr(perf_env.os, "name", "nt")
    assert perf_env.venv_python(tmp_path) == tmp_path / "Scripts" / "python.exe"
    monkeypatch.setattr(perf_env.os, "name", "posix")
    assert perf_env.venv_python(tmp_path) == tmp_path / "bin" / "python"


def test_candidate_env_imports_this_checkout_compiled():
    """The checkout comes first on PYTHONPATH and the pure-Python switch is off."""
    env = perf_env.candidate_env(ROOT)
    assert env["PYTHONPATH"].split(perf_env.os.pathsep)[0] == str(ROOT)
    assert "MODELLY_PURE_PYTHON" not in env


def test_install_hooks_sets_the_hooks_path(tmp_path):
    """install-hooks points core.hooksPath at .githooks."""
    subprocess.run([shutil.which("git"), "init", "-q", str(tmp_path)], check=True)
    (tmp_path / hooks.HOOKS_DIR).mkdir()
    (tmp_path / hooks.HOOKS_DIR / "pre-commit").write_text(
        "#!/bin/sh\n", encoding="utf-8"
    )
    assert hooks.install_hooks(tmp_path, io.StringIO()) == hooks.EXIT_PASSED
    assert perf_env.git(tmp_path, "config", "core.hooksPath") == hooks.HOOKS_DIR


def test_hook_script_and_ops_ship_with_the_checkout():
    """The hook calls the guard; the operations file defines every operation."""
    hook = (ROOT / hooks.HOOKS_DIR / "pre-commit").read_text(encoding="utf-8")
    assert "-m modelly.dev perf --staged" in hook
    sys.path.insert(0, str(ROOT / perf.OPS_DIR))
    try:
        import ops  # noqa: PLC0415
    finally:
        sys.path.pop(0)
    names = ops.operations()
    assert "numpy control" in names and "column read" in names and len(names) >= 15


def test_cli_parses_perf_options(monkeypatch):
    """``perf`` passes --against, --staged, --pairs and --threshold through."""
    seen = {}
    monkeypatch.setattr(
        "modelly.dev.__main__.main_perf",
        lambda root, args: seen.update(vars(args)) or 0,
    )
    assert (
        main(
            [
                "perf",
                "--against",
                "1.2.0",
                "--staged",
                "--pairs",
                "4",
                "--threshold",
                "1.05",
            ]
        )
        == 0
    )
    assert seen["against"] == "1.2.0" and seen["staged"] and seen["pairs"] == 4
    assert seen["threshold"] == pytest.approx(1.05)


def test_worker_times_operations_end_to_end():
    """A real worker on this checkout calibrates and times one operation."""
    worker = perf.Worker(
        sys.executable, ROOT / perf.OPS_DIR, perf_env.candidate_env(ROOT)
    )
    try:
        number = worker.ask("random.random", 0)
        assert number >= 1 and worker.ask("random.random", number) > 0
    finally:
        worker.close()


def test_main_perf_forwards_its_arguments(monkeypatch):
    """main_perf hands the parsed options to run_perf."""
    seen = {}
    monkeypatch.setattr(hooks, "run_perf", lambda root, out, **kw: seen.update(kw) or 0)
    args = SimpleNamespace(staged=True, against="1.3.0", pairs=3, threshold=1.1)
    assert hooks.main_perf(ROOT, args) == 0
    assert seen == {"staged": True, "against": "1.3.0", "pairs": 3, "threshold": 1.1}
