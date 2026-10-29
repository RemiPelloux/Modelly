"""Tests for ``modelly bench --against``: paired rounds against a release."""

import json
import os
import sys

import pytest

from modelly.bench import against
from modelly.bench.__main__ import EXIT_OK, EXIT_REGRESSION, EXIT_USAGE, main
from modelly.dev.perf_env import PerfEnvError

REGISTRY = """\
PLAYBOOKS = {
    "toy": {
        "variants": {"mesa": "m", "modelly": "a", "modelly-cells": "b"},
        "sizes": {"tiny": {"n": 3}},
    },
}
"""

# Reports the CPU seconds and population its environment says, and which side it is.
WORKER = """\
import json, os, sys
playbook, variant, seed, size = sys.argv[1:5]
side = os.environ["SIDE"]
if os.environ.get("FAIL_" + side) == variant:
    sys.exit("no module named " + variant)
cpu = float(os.environ.get("CPU_" + side, "1.0"))
population = int(os.environ.get("POP_" + side, "3"))
with open(os.environ["LOG"], "a") as log:
    log.write(json.dumps([side, variant]) + "\\n")
row = {"playbook": playbook, "variant": variant, "cpu_seconds": cpu, "run_seconds": cpu,
       "population": population, "stats": {"mean": 1.5}}
print("RESULT " + json.dumps(row))
"""


@pytest.fixture
def playbooks(tmp_path, monkeypatch):
    """A toy playbook directory, and two fake sides that differ only by environment."""
    directory = tmp_path / "playbooks"
    directory.mkdir()
    (directory / "registry.py").write_text(REGISTRY, encoding="utf-8")
    (directory / "worker.py").write_text(WORKER, encoding="utf-8")
    log = tmp_path / "log.jsonl"

    def prepare(version, start):
        assert version == "9.9.9"
        base = {**os.environ, "LOG": str(log)}  # read now: tests set variables later
        release = {**base, "SIDE": "RELEASE"}
        return against.Sides(
            version, sys.executable, release, {**base, "SIDE": "CHECKOUT"}
        )

    monkeypatch.setattr(against, "prepare", prepare)
    return directory, log


def run(directory, *extra):
    """``modelly bench --against 9.9.9`` on the toy playbook, four rounds, unpinned."""
    argv = ["--playbooks", str(directory), "--size", "tiny", "--rounds", "4"]
    return main([*argv, "--no-pin", "--against", "9.9.9", *extra], prog="modelly bench")


def test_sides_alternate_and_equal_runs_pass(playbooks, capsys):
    """Each round runs both sides, the first side swapping; Mesa is not paired."""
    directory, log = playbooks
    assert run(directory) == EXIT_OK
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert {variant for _, variant in calls} == {"modelly", "modelly-cells"}
    # The release side runs each variant once first, to see that it can.
    assert calls[:2] == [["RELEASE", "modelly"], ["RELEASE", "modelly-cells"]]
    calls = calls[2:]
    firsts = [calls[i][0] for i in range(0, len(calls), 2)]
    assert firsts == ["RELEASE", "RELEASE", "CHECKOUT", "CHECKOUT"] * 2
    out = capsys.readouterr().out
    assert "| toy/modelly | 1.000 | 1.000 | 1.000 | 1.000 to 1.000 | identical |" in out
    assert "no variant slower than 9.9.9" in out


def test_a_slower_checkout_fails(playbooks, monkeypatch, capsys):
    """Median and lower quartile above the threshold: slower, exit 1."""
    directory, _ = playbooks
    monkeypatch.setenv("CPU_CHECKOUT", "1.25")
    assert run(directory) == EXIT_REGRESSION
    assert (
        "slower than 9.9.9: toy/modelly, toy/modelly-cells" in capsys.readouterr().out
    )
    assert run(directory, "--threshold", "0.3") == EXIT_OK


def test_different_results_fail(playbooks, monkeypatch, capsys):
    """Times of runs that computed different things are not comparable."""
    directory, _ = playbooks
    monkeypatch.setenv("POP_CHECKOUT", "4")
    assert run(directory, "--only", "toy:modelly") == EXIT_REGRESSION
    out = capsys.readouterr().out
    assert "DIFFER" in out and "results differ: toy/modelly" in out


def test_a_release_that_cannot_be_built_is_a_usage_error(
    playbooks, monkeypatch, capsys
):
    """The builder's error (a missing tag, no compiler) is reported, exit 2."""
    directory, _ = playbooks

    def unbuildable(version, start):
        raise PerfEnvError(f"could not build modelly-abm {version} from tag v{version}")

    monkeypatch.setattr(against, "prepare", unbuildable)
    assert run(directory) == EXIT_USAGE
    assert "could not build modelly-abm 9.9.9" in capsys.readouterr().err


def test_a_variant_the_release_cannot_run_is_skipped(playbooks, monkeypatch, capsys):
    """A variant added since the release is reported as skipped, not as a failure."""
    directory, log = playbooks
    monkeypatch.setenv("FAIL_RELEASE", "modelly-cells")
    assert run(directory) == EXIT_OK
    out = capsys.readouterr().out
    assert (
        "skipped (not run by 9.9.9): toy/modelly-cells: no module named modelly-cells"
        in out
    )
    assert "| toy/modelly |" in out and "| toy/modelly-cells |" not in out
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert ["RELEASE", "modelly-cells"] not in rows


def test_pairing_statistics():
    """Ratios, quartiles and the slower criterion of the performance guard."""
    pairing = against.Pairing("p/v", [1.0, 1.0, 2.0, 2.0], [1.1, 0.9, 2.4, 2.0], True)
    assert pairing.ratios == pytest.approx([1.1, 0.9, 1.2, 1.0])
    low, median, high = pairing.quartiles()
    assert low < 1.0 < median < high
    assert not pairing.slower(0.0)  # the lower quartile is below 1
    assert against.Pairing("p/v", [1.0], [1.5], True).slower(0.1)
