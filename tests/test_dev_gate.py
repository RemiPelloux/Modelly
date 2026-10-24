"""Tests for ``python -m modelly.dev gate``: the stages, the skips, the summary, the CLI."""

import io
import sys
from pathlib import Path

import pytest

from modelly.dev import gate
from modelly.dev.__main__ import main

ROOT = Path(__file__).resolve().parents[1]


def test_stages_match_the_bash_gate():
    """The same stage names, in the same order, as scripts/ci-local.sh."""
    script = (ROOT / "scripts" / "ci-local.sh").read_text(encoding="utf-8")
    assert f"STAGES=({' '.join(gate.STAGES)})" in script


def test_stage_commands_use_this_interpreter():
    """Every command runs with the current Python; the test stage refreshes the badge."""
    for name in gate.STAGES:
        for command in gate.stage_commands(name):
            assert command[0] == sys.executable
    test, badge = gate.stage_commands("test")
    assert test[1:3] == ["-m", "pytest"] and "--cov" in test
    assert badge[1:] == ["scripts/coverage_badge.py", gate.COVERAGE_XML, gate.BADGE]
    assert gate.stage_commands("audit")[0][1:] == [gate.AUDIT, "audit"]


def test_optional_tests_skipped_without_solara(monkeypatch):
    """tests/viz and tests/examples are ignored when solara cannot be imported."""
    monkeypatch.setattr(gate.importlib.util, "find_spec", lambda name: None)
    assert gate.optional_skips() == ["--ignore=tests/viz", "--ignore=tests/examples"]
    assert "--ignore=tests/viz" in gate.stage_commands("test")[0]
    monkeypatch.setattr(gate.importlib.util, "find_spec", lambda name: object())
    assert gate.optional_skips() == []


def test_run_gate_reports_each_stage():
    """A failing command fails its stage, stops that stage, and the gate exits 1."""
    calls = []

    def runner(command, cwd):
        calls.append(command)
        return 1 if "format" in command else 0

    out = io.StringIO()
    status = gate.run_gate(["lint", "format", "audit"], ROOT, out, runner)
    assert status == gate.EXIT_FAILED
    text = out.getvalue()
    assert "<== lint: passed" in text and "<== format: failed" in text
    assert "  failed  format" in text and "  passed  audit" in text
    assert len(calls) == len(["lint", "format", "audit"])


def test_test_stage_stops_before_the_badge_when_tests_fail():
    """The badge is only refreshed from a passing test run."""
    calls = []

    def runner(command, cwd):
        calls.append(command)
        return 1

    assert not gate.run_stage("test", ROOT, runner)
    assert len(calls) == 1


def test_cli_list_unknown_and_a_real_stage(capsys):
    """--list prints the stages, an unknown stage is a usage error, audit runs for real."""
    assert main(["gate", "--list"]) == gate.EXIT_PASSED
    assert capsys.readouterr().out.split() == list(gate.STAGES)
    assert main(["gate", "lint", "nope"]) == gate.EXIT_USAGE
    assert "Unknown stage: nope" in capsys.readouterr().err
    assert main(["gate", "audit"]) == gate.EXIT_PASSED


def test_not_a_checkout(monkeypatch, tmp_path, capsys):
    """Outside a source checkout the gate explains itself and exits 2."""
    monkeypatch.setattr(gate, "AUDIT", "no/such/script.py")
    with pytest.raises(gate.GateError):
        gate.checkout_root()
    assert main(["gate"]) == gate.EXIT_USAGE
    assert "not a Modelly checkout" in capsys.readouterr().err
