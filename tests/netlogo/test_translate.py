"""Tests for the translation: the bundled models run and behave like NetLogo's."""

import shutil
import statistics
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from modelly.lint import lint_source
from modelly.netlogo import translate
from tests.netlogo.shared import bundled, load, translated

REPO = Path(__file__).resolve().parents[2]
EXTENT = 50  # a 101 x 101 forest: big enough for a sharp percolation transition
SEEDS = (1, 2, 3)
SHEEP_STEPS = 100


def burned(module, density: float, seed: int) -> float:
    """The share of trees a translated Fire run burns."""
    scenario = module.FireScenario(
        rng=seed,
        density=density,
        min_pxcor=-EXTENT,
        max_pxcor=EXTENT,
        min_pycor=-EXTENT,
        max_pycor=EXTENT,
    )
    model = module.FireModel(scenario)
    while model.running:
        model.step()
    return model.burned_trees / model.initial_trees


def wolf_sheep_data(module, seed: int) -> pd.DataFrame:
    """The populations of a translated Wolf Sheep run of SHEEP_STEPS ticks."""
    model = module.WolfSheepModel(module.WolfSheepScenario(rng=seed))
    for _ in range(SHEEP_STEPS):
        model.step()
    return model.datacollector.get_model_vars_dataframe()


@pytest.mark.parametrize("stem", ["fire", "wolf_sheep"])
def test_bundled_models_translate_cleanly(stem):
    """Every line is translated, and the output passes modelly lint and compiles."""
    translation = translate(bundled(stem), stem)
    assert translation.untranslated == []
    assert lint_source(translation.source) == []
    compile(translation.source, f"{stem}.py", "exec")


@pytest.mark.parametrize("stem", ["fire", "wolf_sheep"])
def test_output_passes_ruff_with_the_repository_rules(stem, tmp_path):
    """The generated module is clean under this repository's ruff configuration."""
    ruff = shutil.which("ruff") or REPO / ".venv" / "bin" / "ruff"
    if not Path(ruff).exists():
        pytest.skip("ruff is not installed")
    path = tmp_path / f"{stem}.py"
    path.write_text(translate(bundled(stem), stem).source, encoding="utf-8")
    config = REPO / "pyproject.toml"
    result = subprocess.run(
        [str(ruff), "check", "--config", str(config), "--no-cache", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_fire_percolation_threshold(tmp_path):
    """Few trees burn well below 59% density, almost all above: the sharp transition."""
    module = translated("fire", tmp_path)
    share = {
        density: statistics.mean(burned(module, density, seed) for seed in SEEDS)
        for density in (50, 55, 63, 70)
    }
    assert share[50] < 0.2
    assert share[55] < 0.35
    assert share[63] > 0.8
    assert share[70] > 0.9
    assert share[63] - share[55] > 0.5


def test_wolf_sheep_runs_and_reproduces(tmp_path):
    """Both populations stay alive under the default sliders; a seed fixes the run."""
    module = translated("wolf_sheep", tmp_path)
    data = wolf_sheep_data(module, seed=1)
    assert len(data) == SHEEP_STEPS + 1
    assert (data["sheep"] > 0).all() and (data["wolves"] > 0).all()
    assert data["sheep"].nunique() > 1  # the populations move
    pd.testing.assert_frame_equal(data, wolf_sheep_data(module, seed=1))
    assert not data.equals(wolf_sheep_data(module, seed=2))


def test_unsupported_lines_are_kept_and_reported(tmp_path):
    """A primitive outside the subset is a NETLOGO comment and an issue, not a gap."""
    source = (
        "globals [g]\nto setup\n  set g 1\n  layout-circle turtles 5\nend\n"
        "to go\n  set g g + 1\n  tick\nend"
    )
    translation = translate(source, "demo")
    assert [issue.line for issue in translation.untranslated] == [4]
    assert "# NETLOGO line 4, not translated" in translation.source
    assert "layout-circle turtles 5" in translation.source
    model = load(translation, tmp_path).DemoModel()
    model.step()
    assert model.g == 2 and model.ticks == 1


def test_die_stops_the_agent_and_outer_locals_are_nonlocal(tmp_path):
    """A turtle that dies in a procedure runs no further; ``set`` reaches outer ``let``."""
    source = (
        "globals [survivors total]\nturtles-own [weak]\n"
        "to setup\n  create-turtles 10 [ set weak who mod 2 ]\n  reset-ticks\nend\n"
        "to go\n  let n 0\n  ask turtles [ check set n n + 1 ]\n"
        "  set survivors n\n  set total count turtles\n  tick\nend\n"
        "to check\n  if weak = 1 [ die ]\nend"
    )
    translation = translate(source, "demo")
    assert translation.untranslated == []
    assert "nonlocal n" in translation.source
    model = load(translation, tmp_path).DemoModel()
    model.step()
    assert model.survivors == model.total == 5


def test_myself_ternary_and_context_errors(tmp_path):
    """``myself`` is the asking agent; a turtle command run by the observer is reported."""
    source = (
        "globals [g]\nturtles-own [owner]\n"
        "to setup\n  create-turtles 3\n  ask turtles [ ask turtles-here [ set owner myself ] ]\n"
        "  ifelse g > 0 [ set g 1 ] [ set g 2 ]\n  fd 1\nend"
    )
    translation = translate(source, "demo")
    assert "self.g = 1 if self.g > 0 else 2" in translation.source
    assert [issue.line for issue in translation.untranslated] == [7]
    model = load(translation, tmp_path).DemoModel()
    assert {t.owner.unique_id for t in model.turtles()} <= {
        t.unique_id for t in model.turtles()
    }
    assert model.g == 2
