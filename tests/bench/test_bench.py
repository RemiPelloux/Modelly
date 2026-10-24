"""Tests for ``modelly bench``: runs, history, baselines, regressions and pinning."""

import json
import sys
from pathlib import Path

import pytest

from modelly.bench import history, pinning
from modelly.bench.__main__ import EXIT_OK, EXIT_REGRESSION, EXIT_USAGE, main
from modelly.bench.playbooks import load_registry, select_variants

REPO_PLAYBOOKS = Path(__file__).resolve().parents[2] / "benchmarks" / "playbooks"

REGISTRY = """\
PLAYBOOKS = {
    "toy": {
        "variants": {"mesa": "m", "modelly": "a", "modelly-cells": "b"},
        "sizes": {"tiny": {"n": 3}},
    },
    "other": {"variants": {"modelly": "a"}, "sizes": {"tiny": {"n": 1}}},
}
"""

# A worker that reports the CPU seconds it is told to (FAKE_CPU), or fails on request.
WORKER = """\
import json, os, sys
playbook, variant, seed, size = sys.argv[1:5]
if os.environ.get("FAKE_FAIL") == variant:
    sys.exit("boom")
cpu = float(os.environ.get("FAKE_CPU", "1.0"))
row = {"playbook": playbook, "variant": variant, "cpu_seconds": cpu, "population": 3}
print("RESULT " + json.dumps(row))
"""


@pytest.fixture
def playbooks(tmp_path):
    """A playbook directory with two tiny playbooks and a scripted worker."""
    directory = tmp_path / "playbooks"
    directory.mkdir()
    (directory / "registry.py").write_text(REGISTRY, encoding="utf-8")
    (directory / "worker.py").write_text(WORKER, encoding="utf-8")
    return directory


def bench(playbooks, tmp_path, *extra):
    """Run ``modelly bench`` on the toy playbooks with a history in tmp_path."""
    argv = ["--playbooks", str(playbooks), "--size", "tiny", "--rounds", "2"]
    argv += ["--history", str(tmp_path / "h" / "history.jsonl"), "--no-pin", *extra]
    return main(argv, prog="modelly bench")


def test_runs_every_modelly_variant_and_appends_one_line(playbooks, tmp_path, capsys):
    """Mesa is skipped without MESA_PYTHON; the history gets one entry per invocation."""
    assert bench(playbooks, tmp_path) == EXIT_OK
    assert bench(playbooks, tmp_path, "--label", "second") == EXIT_OK
    entries = history.load(tmp_path / "h" / "history.jsonl")
    assert len(entries) == 2
    assert set(entries[0]["results"]) == {
        "toy/modelly",
        "toy/modelly-cells",
        "other/modelly",
    }
    assert entries[0]["results"]["toy/modelly"]["cpu_seconds"] == [1.0, 1.0]
    assert entries[1]["label"] == "second"
    assert "not pinned (--no-pin)" in capsys.readouterr().out


def test_regression_against_the_baseline_exits_1(
    playbooks, tmp_path, monkeypatch, capsys
):
    """Slower than the labelled baseline beyond the threshold is a regression."""
    assert bench(playbooks, tmp_path, "--label", "base") == EXIT_OK
    monkeypatch.setenv("FAKE_CPU", "1.05")
    assert bench(playbooks, tmp_path, "--baseline", "base") == EXIT_OK
    monkeypatch.setenv("FAKE_CPU", "1.5")
    assert (
        bench(playbooks, tmp_path, "--baseline", "base", "--no-record")
        == EXIT_REGRESSION
    )
    out = capsys.readouterr().out
    assert "REGRESSION" in out and "1.50x" in out
    assert len(history.load(tmp_path / "h" / "history.jsonl")) == 2
    assert (
        bench(playbooks, tmp_path, "--baseline", "0", "--threshold", "0.6") == EXIT_OK
    )


def test_only_filters_and_json_output(playbooks, tmp_path, capsys):
    """--only takes a playbook or playbook:variant; --format json holds the entry."""
    assert (
        bench(playbooks, tmp_path, "--only", "toy:modelly-cells", "--format", "json")
        == 0
    )
    document = json.loads(capsys.readouterr().out)
    assert list(document["entry"]["results"]) == ["toy/modelly-cells"]
    assert document["changes"][0]["baseline"] is None


def test_mesa_runs_when_mesa_python_is_set(playbooks, monkeypatch):
    """MESA_PYTHON adds the Mesa variant, run by that interpreter."""
    monkeypatch.setenv("MESA_PYTHON", sys.executable)
    keys = [v.key for v in select_variants(load_registry(playbooks), ["toy"], "tiny")]
    assert keys == ["toy/mesa", "toy/modelly", "toy/modelly-cells"]


@pytest.mark.parametrize(
    "extra",
    [
        ("--only", "nope"),
        ("--size", "huge"),
        ("--baseline", "missing"),
        ("--playbooks", "/no/such/dir"),
    ],
)
def test_usage_errors_exit_2(playbooks, tmp_path, extra, capsys):
    """Unknown names, sizes, baselines and directories are usage errors."""
    assert bench(playbooks, tmp_path, *extra) == EXIT_USAGE
    assert "modelly bench:" in capsys.readouterr().err


def test_a_failing_run_is_reported(playbooks, tmp_path, monkeypatch, capsys):
    """A worker that exits without a RESULT line stops the bench with its stderr."""
    monkeypatch.setenv("FAKE_FAIL", "modelly-cells")
    assert bench(playbooks, tmp_path) == EXIT_USAGE
    err = capsys.readouterr().err
    assert "toy/modelly-cells failed" in err and "boom" in err


def test_pinning_follows_the_platform(monkeypatch):
    """Pinned where psutil and the OS allow it; macOS and a missing psutil say why not."""
    monkeypatch.setattr(pinning.sys, "platform", "darwin")
    assert pinning.choose(None).core is None
    assert "macOS" in pinning.choose(None).note
    monkeypatch.setattr(pinning.sys, "platform", "linux")
    monkeypatch.setattr(pinning, "_process", lambda: None)
    assert "psutil is not installed" in pinning.choose(None).note


def test_pinning_sets_and_restores_the_affinity():
    """Inside ``pinned`` the process runs on one core; afterwards on its old set."""
    process = pinning._process()
    if process is None or not hasattr(process, "cpu_affinity"):
        pytest.skip("no CPU affinity on this system")
    before = process.cpu_affinity()
    chosen = pinning.choose(before[0])
    with pinning.pinned(chosen):
        assert process.cpu_affinity() == [before[0]]
    assert process.cpu_affinity() == before
    with pytest.raises(ValueError, match="not one of"):
        pinning.choose(max(before) + 1)


@pytest.mark.skipif(
    not REPO_PLAYBOOKS.is_dir(), reason="needs the repository's playbooks"
)
def test_a_real_playbook_at_the_small_size(tmp_path):
    """The repository's playbooks run through the bench and record a population."""
    path = tmp_path / "history.jsonl"
    argv = ["--playbooks", str(REPO_PLAYBOOKS), "--size", "small", "--rounds", "1"]
    argv += ["--only", "boltzmann_wealth:modelly", "--history", str(path)]
    assert main(argv) == EXIT_OK
    (entry,) = history.load(path)
    result = entry["results"]["boltzmann_wealth/modelly"]
    assert result["population"] == 500 and result["median"] > 0
