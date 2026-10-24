"""``verify``: a rerun matches, a changed output is found, tolerances apply."""

import pandas as pd
import pytest
from conftest import SCHELLING

from modelly.provenance import (
    Difference,
    RunSpec,
    Tolerance,
    first_difference,
    read_manifest,
    run_study,
    verify,
)
from modelly.provenance.outputs import read_table

NUDGE = 1e-9


def _rewrite(run, table: str, change) -> None:
    """Apply ``change`` to one recorded output table, in its own format."""
    item = next(i for i in read_manifest(run)["outputs"] if i["table"] == table)
    path = run / item["path"]
    frame = change(read_table(path, item["format"]))
    if item["format"] == "parquet":
        frame.to_parquet(path, index=False)
    else:
        frame.to_csv(path, index=False)


def test_a_rerun_matches(boltzmann_run):
    """The recorded Boltzmann run reproduces exactly."""
    result = verify(boltzmann_run / "manifest.json")
    assert result.matches
    assert result.notes == []


def test_schelling_rerun_matches(tmp_path):
    """A second example, given as a dotted module, reproduces too."""
    run_study(RunSpec(SCHELLING, out=tmp_path / "out", steps=3, seed=2))
    assert verify(tmp_path / "out").matches


def test_a_changed_output_is_reported(boltzmann_run):
    """The first differing table, column and row are named."""

    def change(frame):
        frame.loc[2, "Gini"] += 1
        return frame

    _rewrite(boltzmann_run, "model", change)
    result = verify(boltzmann_run)
    assert not result.matches
    assert result.difference.table == "model"
    assert result.difference.column == "Gini"
    assert result.difference.row == 2
    assert "table 'model', column 'Gini', row 2" in str(result.difference)


def test_tolerance_accepts_small_changes(boltzmann_run):
    """A change below rtol passes; the default (exact) does not."""

    def change(frame):
        frame["Gini"] *= 1 + NUDGE
        return frame

    _rewrite(boltzmann_run, "model", change)
    assert not verify(boltzmann_run).matches
    assert verify(boltzmann_run, Tolerance(rtol=NUDGE * 10)).matches


def test_changed_code_is_a_note(tiny_model, tmp_path):
    """Editing the model after the run is noted; the changed behaviour is found."""
    run_study(RunSpec(f"{tiny_model}:Walk", out=tmp_path / "out", steps=3, seed=1))
    source = tiny_model.read_text(encoding="utf-8")
    tiny_model.write_text(
        source.replace("self.random.random()", "2.0"), encoding="utf-8"
    )
    result = verify(tmp_path / "out")
    assert "code file changed or missing: walk.py" in result.notes
    assert result.difference.table == "agents"


def test_missing_output_is_a_difference(boltzmann_run):
    """A recorded output that was deleted is reported as missing."""
    (boltzmann_run / "model.parquet").unlink(missing_ok=True)
    (boltzmann_run / "model.csv").unlink(missing_ok=True)
    assert "missing" in verify(boltzmann_run).difference.message


@pytest.mark.parametrize(
    ("actual", "expected_text"),
    [
        (pd.DataFrame({"a": [1, 2], "c": [3, 4]}), "columns differ"),
        (pd.DataFrame({"a": [1], "b": ["x"]}), "row counts differ"),
        (pd.DataFrame({"a": [1, 2], "b": ["x", "z"]}), "expected 'y', got 'z'"),
    ],
)
def test_first_difference(actual, expected_text):
    """Columns, then row counts, then values are compared."""
    expected = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    difference = first_difference("t", expected, actual)
    assert isinstance(difference, Difference)
    assert expected_text in difference.message


def test_missing_values_match():
    """NaN in both tables is not a difference."""
    frame = pd.DataFrame({"a": [1.0, float("nan")], "b": [None, "x"]})
    assert first_difference("t", frame, frame.copy()) is None
