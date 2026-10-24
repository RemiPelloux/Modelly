"""Tests for ``modelly experiment``: run, status, dry runs and exit codes."""

import textwrap

import pytest

from modelly.__main__ import main as modelly_main
from modelly.experiments.__main__ import EXIT_FAILED, EXIT_OK, EXIT_USAGE, main

pytest.importorskip("pyarrow")
pytest.importorskip("duckdb")

SPEC = """
[experiment]
model = "tests.experiments.models:Walk"
steps = 3
replicates = 2
outputs = ["mean", "spread"]
store = "runs"

[space]
drift = {{ min = 0.0, max = 1.0 }}
fail = {fail}

[design]
kind = "halton"
n = 3

[run]
executor = "serial"
"""


def spec(tmp_path, fail="false"):
    """A spec file in ``tmp_path``."""
    path = tmp_path / "study.toml"
    path.write_text(textwrap.dedent(SPEC.format(fail=fail)), encoding="utf-8")
    return str(path)


def test_run_then_resume(tmp_path, capsys):
    """A run finishes everything; a second run finds it all in the store."""
    path = spec(tmp_path)
    assert modelly_main(["experiment", "run", path]) == EXIT_OK
    assert (
        "6 runs finished, 0 failed, 0 already in the store (of 6)"
        in capsys.readouterr().out
    )
    assert (
        main(["run", path, "--executor", "threads", "--max-parallel", "2"]) == EXIT_OK
    )
    assert "0 runs finished, 0 failed, 6 already" in capsys.readouterr().out
    assert main(["status", path]) == EXIT_OK
    assert (
        "3 points x 2 replicates: 6 finished, 0 failed, 0 pending"
        in capsys.readouterr().out
    )


def test_dry_run_lists_pending_runs(tmp_path, capsys):
    """--dry-run lists every pending run and runs nothing."""
    path = spec(tmp_path)
    assert main(["run", path, "--dry-run"]) == EXIT_OK
    out = capsys.readouterr().out
    assert out.startswith("6 runs pending on serial") and "0-1  seed" in out
    assert not (tmp_path / "runs").exists()


def test_failed_runs_exit_one(tmp_path, capsys):
    """Failed runs are listed and make the exit status 1, for run and status."""
    path = spec(tmp_path, fail="true")
    assert main(["run", path]) == EXIT_FAILED
    assert "failed: 0-0" in capsys.readouterr().out
    assert main(["status", path]) == EXIT_FAILED
    assert "6 failed, 6 pending" in capsys.readouterr().out


def test_raise_mode_exits_one(tmp_path, capsys):
    """on_error = "raise" stops at the first failure with exit 1."""
    path = tmp_path / "raise.toml"
    text = SPEC.format(fail="true").replace(
        'store = "runs"', 'store = "runs"\non_error = "raise"'
    )
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    assert main(["run", str(path)]) == EXIT_FAILED
    assert "asked to fail" in capsys.readouterr().err


def test_usage_errors_exit_two(tmp_path, capsys):
    """A missing file, a bad spec or another experiment's store exit 2."""
    assert main(["run", str(tmp_path / "missing.toml")]) == EXIT_USAGE
    bad = tmp_path / "bad.toml"
    bad.write_text("[experiment\n", encoding="utf-8")
    assert main(["status", str(bad)]) == EXIT_USAGE
    path = spec(tmp_path)
    assert main(["run", path]) == EXIT_OK
    other = (
        (tmp_path / "study.toml").read_text(encoding="utf-8").replace("n = 3", "n = 4")
    )
    (tmp_path / "study.toml").write_text(other, encoding="utf-8")
    assert main(["run", path]) == EXIT_USAGE
    assert "different experiment" in capsys.readouterr().err
    with pytest.raises(SystemExit) as stop:
        main([])
    assert stop.value.code == EXIT_USAGE


def test_help_has_examples_and_exit_codes(capsys):
    """The help shows examples, a spec, the executors and the exit codes."""
    with pytest.raises(SystemExit):
        main(["run", "--help"], prog="modelly experiment")
    out = capsys.readouterr().out
    assert out.startswith("usage: modelly experiment run")
    for text in ("examples:", "[space]", "executors: ", "exit codes:", "slurm"):
        assert text in out
