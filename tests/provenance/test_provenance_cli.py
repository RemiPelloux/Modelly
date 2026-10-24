"""``modelly run / verify / bundle / odd``: output and documented exit codes."""

import pandas as pd
import pytest
from conftest import BOLTZMANN

from modelly.__main__ import main
from modelly.provenance.commands.common import (
    EXIT_FAILED,
    EXIT_MODEL_ERROR,
    EXIT_OK,
    EXIT_USAGE,
)


def _run(tmp_path, *extra):
    """``modelly run`` on Boltzmann into tmp_path/runs; the exit status."""
    argv = [
        "run",
        BOLTZMANN,
        "--steps",
        "3",
        "--seed",
        "1",
        "--out",
        str(tmp_path / "runs"),
    ]
    return main([*argv, *extra])


def test_run_then_verify(tmp_path, capsys):
    """Run writes the manifest; verify prints 'outputs match' and exits 0."""
    assert _run(tmp_path, "--param", "n=20") == EXIT_OK
    assert "manifest.json" in capsys.readouterr().out
    assert main(["verify", str(tmp_path / "runs" / "manifest.json")]) == EXIT_OK
    assert capsys.readouterr().out == "outputs match\n"


def test_verify_reports_a_difference(tmp_path, capsys):
    """A tampered output makes verify print the difference and exit 1."""
    assert _run(tmp_path) == EXIT_OK
    output = next(p for p in (tmp_path / "runs").iterdir() if p.stem == "model")
    if output.suffix == ".csv":
        output.write_text("Gini\n" + "0.5\n" * 4, encoding="utf-8")
    else:
        pd.DataFrame({"Gini": [0.5] * 4}).to_parquet(output, index=False)
    capsys.readouterr()
    assert main(["verify", str(tmp_path / "runs"), "--rtol", "0"]) == EXIT_FAILED
    assert (
        "outputs differ: table 'model', column 'Gini', row 0" in capsys.readouterr().out
    )


def test_bundle_and_odd(tmp_path, capsys):
    """Bundle writes the zip; odd prints the skeleton."""
    assert _run(tmp_path) == EXIT_OK
    zip_path = tmp_path / "study.zip"
    assert main(["bundle", str(tmp_path / "runs"), "--out", str(zip_path)]) == EXIT_OK
    assert zip_path.is_file()
    capsys.readouterr()
    assert main(["odd", BOLTZMANN, "--seed", "1"]) == EXIT_OK
    assert capsys.readouterr().out.startswith("# ODD protocol: BoltzmannWealth")


@pytest.mark.parametrize(
    "argv",
    [
        ["run", "nope.py:Model", "--steps", "1", "--out", "unused"],
        ["verify", "no/such/manifest.json"],
        ["bundle", "no/such/run", "--out", "unused.zip"],
        ["odd", "nope.py:Model"],
    ],
)
def test_usage_errors_exit_2(argv, capsys):
    """A target, manifest or run that cannot be found is a usage error."""
    assert main(argv) == EXIT_USAGE
    assert capsys.readouterr().err


def test_model_errors_exit_3(tiny_model, tmp_path, capsys):
    """A model that raises while running is exit 3 with a traceback."""
    argv = ["run", f"{tiny_model}:Broken", "--steps", "1", "--out", str(tmp_path / "o")]
    assert main(argv) == EXIT_MODEL_ERROR
    assert "boom" in capsys.readouterr().err


@pytest.mark.parametrize("name", ["run", "verify", "bundle", "odd"])
def test_help_documents_exit_codes(name, capsys):
    """Each command's --help shows examples and its exit codes."""
    with pytest.raises(SystemExit) as stop:
        main([name, "--help"])
    assert stop.value.code == EXIT_OK
    out = capsys.readouterr().out
    assert out.startswith(f"usage: modelly {name} ")
    assert "examples:" in out and "exit codes:" in out
