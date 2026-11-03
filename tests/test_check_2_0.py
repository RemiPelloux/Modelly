"""``modelly migrate --check-2.0``: every 2.0 change code can show, found with its line."""

from modelly.check_2_0 import CHANGE, NOTE, check
from modelly.migrate import main

PROJECT = """\
from modelly import Model
from modelly.scenarios import Scenario
from modelly.space.geo import ipf
from modelly.visualization import make_space_altair


class Rates(Scenario):
    beta: float = 0.3
    gamma = 0.1


class Town(Model):
    agent_streams = True


class Old(Model):
    pass


def agent_portrayal(agent):
    return {"color": "red"}


def show(renderer, model):
    make_space_altair(model)
    renderer.render(agent_portrayal=agent_portrayal)
    renderer.render()
    renderer.draw_agents()
    draw(model, property_layer_portrayal={"layer": {}})
"""


def test_every_pattern_is_found_on_its_line(tmp_path):
    """Changes with what to write instead; notes for what changes without a warning."""
    (tmp_path / "model.py").write_text(PROJECT, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.12"\n', encoding="utf-8"
    )
    found = {(f.kind, f.line): f.message for f in check([tmp_path])}
    assert "modelly.population" in found[(CHANGE, 3)]
    assert "gamma: type = value" in found[(CHANGE, 9)]
    assert "agent_streams" in found[(NOTE, 16)] and (NOTE, 12) not in found
    assert "AgentPortrayalStyle" in found[(CHANGE, 20)]
    assert "make_altair_space()" in found[(CHANGE, 25)]
    assert "setup_structure()" in found[(CHANGE, 26)] and (CHANGE, 27) not in found
    assert (CHANGE, 28) not in found and "PropertyLayerStyle" in found[(CHANGE, 29)]
    assert any("Python 3.13" in m for (kind, _), m in found.items() if kind == NOTE)


def test_the_command_exits_1_on_changes_and_0_without(tmp_path, capsys):
    """A clean project passes; one change fails, as a test or a hook needs."""
    (tmp_path / "clean.py").write_text(
        "from modelly import Model\n\n\nclass M(Model):\n    agent_streams = True\n"
    )
    assert main(["--check-2.0", str(tmp_path)]) == 0
    assert "0 change(s)" in capsys.readouterr().out
    (tmp_path / "old.py").write_text(
        "from modelly.visualization import make_plot_measure\nmake_plot_measure(1)\n"
    )
    assert main(["--check-2.0", str(tmp_path)]) == 1
    assert "make_mpl_plot_component()" in capsys.readouterr().out
    (tmp_path / "broken.py").write_text("def (:\n")
    assert any(f.message.startswith("not checked") for f in check([tmp_path]))
