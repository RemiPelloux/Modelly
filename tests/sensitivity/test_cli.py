"""Tests for ``modelly sensitivity spec.toml`` and executor independence."""

import pandas as pd
import pytest

from modelly.__main__ import main as umbrella
from modelly.sensitivity import morris
from modelly.sensitivity.__main__ import EXIT_OK, EXIT_USAGE, main
from modelly.sensitivity.spec import load_sensitivity
from tests.sensitivity.models import Response
from tests.sensitivity.test_screening import SPACE

pytest.importorskip("pyarrow")

SPEC = """\
[experiment]
model = "{model}"
steps = 1
seed = 1
outputs = ["value"]

[space]
a = {{ min = 0.0, max = 1.0 }}
b = {{ min = 0.0, max = 1.0 }}
c = {{ min = 0.0, max = 1.0 }}
d = 0.5

[sensitivity]
method = "{method}"
{settings}
"""


def write_spec(folder, method="morris", settings="trajectories = 6", model=None):
    """A sensitivity spec in ``folder``."""
    model = model or "tests.sensitivity.models:Response"
    path = folder / "study.toml"
    text = SPEC.format(model=model, method=method, settings=settings)
    path.write_text(text, encoding="utf-8")
    return path


def test_spec_reads_the_study(tmp_path):
    """The first output is analysed; fixed values stay fixed."""
    method, arguments = load_sensitivity(write_spec(tmp_path))
    assert method is morris
    assert arguments["output"] == "value" and arguments["trajectories"] == 6
    assert list(arguments["space"].dimensions) == ["a", "b", "c"]


def test_cli_prints_and_writes_the_ranking(tmp_path, capsys):
    """The command ranks the parameters, most influential first."""
    out = tmp_path / "ranking.csv"
    assert main([str(write_spec(tmp_path)), "--output", str(out)]) == EXIT_OK
    assert "ranked by mu_star" in capsys.readouterr().out
    assert list(pd.read_csv(out)["parameter"]) == ["a", "b", "c"]
    sobol = ["--method", "sobol", "--executor", "threads", "--max-parallel", "2"]
    assert main([str(write_spec(tmp_path)), *sobol]) == EXIT_USAGE  # trajectories
    spec = write_spec(tmp_path, "sobol", "samples = 16\nbootstrap = 5")
    assert main([str(spec), *sobol]) == EXIT_OK


def test_cli_function_model(tmp_path, capsys):
    """A module:function model is called with the parameters."""
    spec = write_spec(tmp_path, "oat", "levels = 3", "tests.sensitivity.models:linear")
    assert main([str(spec)]) == EXIT_OK
    assert "ranked by effect" in capsys.readouterr().out


def test_cli_usage_errors(tmp_path):
    """Unknown methods and settings, and a missing file, are usage errors."""
    assert main([str(tmp_path / "missing.toml")]) == EXIT_USAGE
    assert main([str(write_spec(tmp_path, "nope"))]) == EXIT_USAGE
    assert main([str(write_spec(tmp_path, settings="colour = 1"))]) == EXIT_USAGE


def test_umbrella_help(capsys):
    """``modelly sensitivity --help`` documents the spec."""
    with pytest.raises(SystemExit):
        umbrella(["sensitivity", "--help"])
    out = capsys.readouterr().out
    assert out.startswith("usage: modelly sensitivity") and "[sensitivity]" in out


def test_same_indices_on_every_executor():
    """Serial, threads and processes give identical elementary effects."""
    settings = {"trajectories": 4, "steps": 1, "seed": 5, "max_parallel": 2}
    serial = morris(Response, SPACE, "value", **settings).table
    for executor in ("threads", "processes"):
        other = morris(Response, SPACE, "value", executor=executor, **settings).table
        pd.testing.assert_frame_equal(other, serial)
