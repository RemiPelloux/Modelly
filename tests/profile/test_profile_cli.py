"""Tests for ``python -m modelly.profile``: targets, parameters, formats and exit codes."""

import json
import textwrap

import pytest

from modelly.profile.__main__ import main
from modelly.profile.loader import TargetError, build_model, load_class, parse_param

MODEL_SOURCE = """
from modelly import Agent, Model


class Scanner(Agent):
    def step(self):
        self.seen = sum(1 for other in self.model.agents if other is not self)


class Crowd(Model):
    def __init__(self, n=20, growth=3, rng=None):
        super().__init__(rng=rng)
        self.growth = growth
        Scanner.create_agents(self, n)

    def step(self):
        self.agents.shuffle_do("step")
        Scanner.create_agents(self, len(self.agents) // self.growth)


class Broken(Model):
    def step(self):
        raise RuntimeError("boom")


NOT_A_MODEL = 3
"""

WOLF_SHEEP = "modelly.examples.advanced.wolf_sheep.model:WolfSheep"


@pytest.fixture
def model_file(tmp_path):
    """The test models, written to a file outside the package."""
    path = tmp_path / "crowd_model.py"
    path.write_text(textwrap.dedent(MODEL_SOURCE), encoding="utf-8")
    return path


def test_text_report_with_params_and_hint(model_file, capsys):
    """Parameters reach the model and a growing scan gets the MDL101 hint."""
    code = main(
        [
            f"{model_file}:Crowd",
            "--steps",
            "8",
            "--param",
            "n=50",
            "--param",
            "growth=2",
            "--seed",
            "1",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("Crowd: 8 step(s) profiled")
    assert "agents 50 at the first step" in out
    assert "MDL101" in out


def test_json_and_csv_formats(model_file, capsys):
    """JSON has the per-step totals; CSV has one step row per step."""
    assert main([f"{model_file}:Crowd", "--steps", "3", "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["model"] == "Crowd" and len(data["steps"]) == 3
    assert main([f"{model_file}:Crowd", "--steps", "3", "--format", "csv"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("step,time,kind,owner,name")
    assert sum(",step,Crowd,step," in line for line in lines) == 3


def test_scenario_model_from_a_module(capsys):
    """A dotted module target, its scenario seeded and sampled."""
    args = [WOLF_SHEEP, "--steps", "5", "--seed", "42", "--param", "width=10"]
    assert main([*args, "--top", "2", "--sample-every", "2"]) == 0
    out = capsys.readouterr().out
    assert "WolfSheep: 3 step(s) profiled, one in 2" in out


@pytest.mark.parametrize(
    "argv",
    [
        ["no_such_file.py:Model"],
        ["no.such.module:Model"],
        ["missing_colon.py"],
        ["{file}:NOT_A_MODEL"],
        ["{file}:Crowd", "--param", "novalue"],
        ["{file}:Crowd", "--param", "unknown=1"],
    ],
)
def test_bad_input_exits_2(argv, model_file, capsys):
    """An unloadable target or a bad parameter is a usage error."""
    argv = [arg.format(file=model_file) for arg in argv]
    assert main(argv) == 2
    assert capsys.readouterr().err.startswith("modelly.profile: ")


def test_model_error_exits_1(model_file, capsys):
    """A model that raises gives its traceback and exit 1."""
    assert main([f"{model_file}:Broken", "--steps", "2"]) == 1
    assert "RuntimeError: boom" in capsys.readouterr().err


@pytest.mark.parametrize("flag", ["--steps", "--top", "--sample-every"])
def test_non_positive_counts_are_rejected(flag, model_file):
    """Counts must be at least 1."""
    with pytest.raises(SystemExit) as exit_info:
        main([f"{model_file}:Crowd", flag, "0"])
    assert exit_info.value.code == 2


def test_help_lists_examples_and_exit_codes(capsys):
    """The help has the examples and the exit codes."""
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    assert "examples:" in out and "exit codes:" in out and "--sample-every" in out


def test_parse_param_values():
    """Values are Python literals, or strings when they are not."""
    assert parse_param("n=5") == ("n", 5)
    assert parse_param("rate=0.5") == ("rate", 0.5)
    assert parse_param("flag=True") == ("flag", True)
    assert parse_param("name=Moore") == ("name", "Moore")
    with pytest.raises(TargetError):
        parse_param("=3")


def test_build_model_routes_params(model_file):
    """Named parameters go to the model, the others to its scenario."""
    crowd = build_model(load_class(f"{model_file}:Crowd"), {"n": 4}, seed=3)
    assert len(crowd.agents) == 4
    wolf_sheep = build_model(load_class(WOLF_SHEEP), {"width": 12}, seed=None)
    assert wolf_sheep.scenario.width == 12
