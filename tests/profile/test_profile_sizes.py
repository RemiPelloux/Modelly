"""Tests for profiling at several sizes: ``compare_sizes`` and ``--sizes`` / ``--size-param``."""

import json
import textwrap

import pytest

from modelly.examples.advanced.wolf_sheep.model import WolfSheep
from modelly.examples.basic.boltzmann_wealth_model.model import BoltzmannWealth
from modelly.profile import compare_sizes
from modelly.profile.__main__ import main
from modelly.profile.loader import TargetError, parameter_names, size_param
from modelly.profile.sizes import STEP_LABEL

MODEL_SOURCE = """
from modelly import Agent, Model


class Scanner(Agent):
    def step(self):
        self.seen = sum(1 for other in self.model.agents if other is not self)


class Local(Agent):
    def step(self):
        self.x = 1


class Crowd(Model):
    def __init__(self, n=20, rng=None):
        super().__init__(rng=rng)
        Scanner.create_agents(self, n)

    def step(self):
        self.agents.shuffle_do("step")


class Flat(Model):
    def __init__(self, num_agents=20, rng=None):
        super().__init__(rng=rng)
        Local.create_agents(self, num_agents)

    def step(self):
        self.agents.shuffle_do("step")


class Sized(Model):
    def __init__(self, walkers=20, rng=None):
        super().__init__(rng=rng)
        Local.create_agents(self, walkers)

    def step(self):
        self.agents.do("step")
"""

SMALL, LARGE = 50, 400
STEPS = "3"


@pytest.fixture
def models(tmp_path, monkeypatch):
    """The test models, importable as ``sized_models``."""
    (tmp_path / "sized_models.py").write_text(textwrap.dedent(MODEL_SOURCE))
    monkeypatch.syspath_prepend(str(tmp_path))
    import sized_models  # noqa: PLC0415 (written by the fixture)

    return sized_models


def test_scan_grows_with_n_and_gets_the_hint(models):
    """The us per agent of a population scan grows about linearly with N."""
    comparison = compare_sizes(lambda n: models.Crowd(n=n, rng=1), [LARGE, SMALL], 3)
    assert comparison.sizes == (SMALL, LARGE)
    by_label = {growth.label: growth for growth in comparison.growths()}
    scan = by_label["Scanner.step (shuffle_do)"]
    assert scan.ratio > 2 and scan.exponent > 0.5
    assert STEP_LABEL in by_label
    hints = comparison.hints()
    assert len(hints) == 1 and "MDL101 / MDL102" in hints[0]
    assert "N=50 us/agent" in comparison.report()


def test_constant_cost_per_agent_gives_no_hint(models):
    """A step that does not look at other agents keeps its cost per agent."""
    comparison = compare_sizes(lambda n: models.Flat(num_agents=n), [SMALL, LARGE], 3)
    assert comparison.hints() == []
    frame = comparison.to_dataframe()
    assert list(frame.columns) == ["operation", "size", "us_per_agent"]
    assert len(frame) == 2 * len(comparison.growths())


@pytest.mark.parametrize("sizes", [[SMALL], [SMALL, SMALL], [0, SMALL]])
def test_needs_two_different_positive_sizes(models, sizes):
    """One size, a repeated size or a zero is rejected before anything runs."""
    with pytest.raises(ValueError, match="at least 2"):
        compare_sizes(models.Flat, sizes)


def test_cli_text_report_finds_n(models, capsys):
    """``--sizes`` with the default parameter name ``n``."""
    target = f"{models.__file__}:Crowd"
    assert main([target, "--sizes", f"{SMALL},{LARGE}", "--steps", STEPS]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"Crowd profiled at N = {SMALL}, {LARGE}")
    assert "MDL101" in out


def test_cli_json_and_csv(models, capsys):
    """JSON has the sizes and growth; CSV one row per operation and size."""
    target = f"{models.__file__}:Flat"
    args = [target, "--sizes", f"{SMALL},{LARGE}", "--steps", STEPS]
    assert main([*args, "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["sizes"] == [SMALL, LARGE] and data["hints"] == []
    assert {"operation", "us_per_agent", "growth"} <= set(data["operations"][0])
    assert main([*args, "--format", "csv"]) == 0
    assert capsys.readouterr().out.startswith("operation,size,us_per_agent")


def test_cli_size_param(models, capsys):
    """``--size-param`` names a parameter none of the defaults match."""
    target = f"{models.__file__}:Sized"
    sizes = ["--sizes", f"{SMALL},{LARGE}", "--steps", STEPS]
    assert main([target, *sizes, "--size-param", "walkers"]) == 0
    assert "Local.step (do)" in capsys.readouterr().out
    assert main([target, *sizes]) == 2
    err = capsys.readouterr().err
    assert "--size-param" in err and "walkers" in err


@pytest.mark.parametrize("value", ["100", "100,100", "100,x", "0,100"])
def test_cli_rejects_bad_sizes(models, value):
    """--sizes needs at least two different positive integers."""
    with pytest.raises(SystemExit) as stop:
        main([f"{models.__file__}:Flat", "--sizes", value])
    assert stop.value.code == 2


def test_size_param_reads_scenario_fields():
    """Scenario fields count as parameters; an explicit name is taken as given."""
    assert "initial_sheep" in parameter_names(WolfSheep)
    assert size_param(BoltzmannWealth) == "n"
    assert size_param(WolfSheep, "initial_sheep") == "initial_sheep"
    with pytest.raises(TargetError, match="initial_sheep"):
        size_param(WolfSheep)


def test_help_shows_a_sizes_example(capsys):
    """The epilog has a --sizes example and the option names the defaults it tries."""
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    assert "--sizes 1000,4000" in out and "num_agents" in out
