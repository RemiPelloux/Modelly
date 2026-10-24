"""Tests for ``modelly calibrate spec.toml`` and the TOML calibration spec."""

import pandas as pd
import pytest

from modelly.__main__ import main as umbrella
from modelly.calibrate import ABCSMC, Prior
from modelly.calibrate.__main__ import EXIT_FAILED, EXIT_OK, EXIT_USAGE, main
from modelly.calibrate.spec import load_calibration
from tests.calibrate.models import SIR
from tests.calibrate.shared import SIR_TRUTH, STEPS, synthetic

pytest.importorskip("pyarrow")

SPEC = """\
[experiment]
model = "tests.calibrate.models:SIR"
steps = {steps}
seed = 7

[space]
beta = {{ min = 0.05, max = 1.0 }}
initial = {{ min = 5, max = 15, integer = true }}
population = 1000

[priors]
gamma = {{ kind = "truncated_normal", mean = 0.15, sd = 0.1, low = 0.01, high = 0.5 }}

[[targets]]
name = "infected"
file = "cases.csv"
column = "cases"
distance = "rmse"

[calibration]
method = "{method}"
{settings}
"""


def write_spec(folder, method="abc_smc", settings="particles = 10\ngenerations = 2"):
    """A spec and its case data in ``folder``."""
    cases = synthetic(SIR, SIR_TRUTH, ["infected"])["infected"]
    pd.DataFrame({"cases": cases}).to_csv(folder / "cases.csv", index=False)
    path = folder / "sir.toml"
    text = SPEC.format(steps=STEPS, method=method, settings=settings)
    path.write_text(text, encoding="utf-8")
    return path


def test_spec_builds_the_calibration(tmp_path):
    """Ranges become uniform priors, integer ranges choices, [priors] the rest."""
    calibration, run, settings = load_calibration(write_spec(tmp_path))
    assert isinstance(calibration, ABCSMC) and calibration.particles == 10
    assert calibration.priors["beta"] == Prior.uniform(0.05, 1.0)
    assert calibration.priors["initial"].arguments["values"] == tuple(range(5, 16))
    assert calibration.priors["gamma"].kind == "truncated_normal"
    assert calibration.fixed == {"population": 1000}
    assert run == {"generations": 2}
    assert settings.executor == "serial"
    assert len(calibration.targets[0].observed) == STEPS


def test_cli_runs_and_writes_samples(tmp_path, capsys):
    """The command prints the summary and writes the samples."""
    out = tmp_path / "posterior.csv"
    assert main([str(write_spec(tmp_path)), "--output", str(out)]) == EXIT_OK
    printed = capsys.readouterr().out
    assert "hdi_low" in printed and "abc-smc" in printed
    assert len(pd.read_csv(out)) == 10


def test_cli_checkpoint_resumes(tmp_path, capsys):
    """--checkpoint saves; a second call resumes from it."""
    spec, checkpoint = write_spec(tmp_path), tmp_path / "sir.ckpt"
    assert main([str(spec), "--checkpoint", str(checkpoint)]) == EXIT_OK
    assert checkpoint.is_file()
    assert main([str(spec), "--checkpoint", str(checkpoint)]) == EXIT_OK
    assert "generations=2" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("method", "settings"),
    [
        ("abc_rejection", "budget = 30\nquantile = 0.2"),
        ("bayes_opt", "evaluations = 3\ninitial = 2"),
    ],
)
def test_other_methods(tmp_path, method, settings):
    """Rejection runs from a spec; Bayesian optimisation refuses the choice prior."""
    code = main([str(write_spec(tmp_path, method, settings))])
    assert code == (EXIT_OK if method == "abc_rejection" else EXIT_USAGE)


def test_usage_errors(tmp_path, capsys):
    """A missing file, an unknown method or setting and a bad checkpoint are usage errors."""
    assert main([str(tmp_path / "missing.toml")]) == EXIT_USAGE
    assert main([str(write_spec(tmp_path, "nope"))]) == EXIT_USAGE
    assert main([str(write_spec(tmp_path, settings="colour = 1"))]) == EXIT_USAGE
    rejection = write_spec(tmp_path, "abc_rejection", "budget = 5")
    assert main([str(rejection), "--checkpoint", str(tmp_path / "c")]) == EXIT_USAGE
    assert "nope" in capsys.readouterr().err


def test_no_sample_is_a_failure(tmp_path):
    """A tolerance no sample meets exits with 1."""
    spec = write_spec(tmp_path, "abc_rejection", "budget = 5\ntolerance = 0.0")
    assert main([str(spec)]) == EXIT_FAILED


def test_umbrella_help(capsys):
    """``modelly calibrate --help`` documents the spec and the exit codes."""
    with pytest.raises(SystemExit):
        umbrella(["calibrate", "--help"])
    out = capsys.readouterr().out
    assert out.startswith("usage: modelly calibrate")
    assert "[[targets]]" in out and "exit codes" in out
