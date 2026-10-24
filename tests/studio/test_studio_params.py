"""Tests for the parameter panel's fields, the Studio config and the target loader."""

import enum
import sys
from pathlib import Path
from typing import Literal

import pytest

import modelly.examples.advanced.wolf_sheep.model as wolf_sheep_model
from modelly.core.model import Model
from modelly.examples import EpsteinCivilViolence, PdGrid, WolfSheep
from modelly.profile.loader import TargetError
from modelly.scenarios import Scenario
from modelly.studio import params
from modelly.studio.config import StudioConfig
from modelly.studio.loader import load_model_class, load_portrayal, module_name


class Colour(enum.Enum):
    """A choice by Enum."""

    RED = "red"
    BLUE = "blue"


class Mixed(Scenario):
    """One field of every kind."""

    flag: bool = True
    count: int = 3
    rate: float = 0.25
    speed: float = 4.5
    label: str = "a"
    mode: Literal["x", "y"] = "x"
    colour: Colour = Colour.RED
    shape: tuple = (1, 2)
    rng: int = 1


class MixedModel(Model):
    """A model with a Scenario and a constructor keyword."""

    def __init__(self, extra: int = 2, scenario: Mixed = Mixed, rng=None):
        """Build nothing."""
        super().__init__(scenario=scenario)
        self.extra = extra


def test_kinds_by_type_and_annotation():
    """Each value type, Literal and Enum picks its widget."""
    found = {p.name: p for p in params.parameters_of(MixedModel)}
    kinds = {name: p.kind for name, p in found.items()}
    assert kinds == {
        "extra": params.INT,
        "flag": params.BOOL,
        "count": params.INT,
        "rate": params.FRACTION,
        "speed": params.FLOAT,
        "label": params.TEXT,
        "mode": params.CHOICE,
        "colour": params.CHOICE,
        "shape": params.FIXED,
    }
    assert found["mode"].choices == ("x", "y")
    assert found["colour"].choices == (Colour.RED, Colour.BLUE)
    assert not found["shape"].editable and found["rate"].editable


def test_rng_is_not_a_parameter():
    """A Scenario's rng field is the seed field, not a panel input."""
    names = {p.name for p in params.parameters_of(EpsteinCivilViolence)}
    assert "rng" not in names and "grid_type" in names


def test_example_parameters():
    """Wolf-Sheep's scenario fields become fields; PdGrid's payoff dict is fixed."""
    names = [p.name for p in params.parameters_of(WolfSheep)]
    assert names[:2] == ["width", "height"]
    payoff = next(p for p in params.parameters_of(PdGrid) if p.name == "payoff")
    assert payoff.kind == params.FIXED


def test_unresolvable_annotations_fall_back():
    """A forward reference that does not resolve leaves the raw annotation."""

    class Odd(Scenario):
        value: "Missing" = 1  # noqa: F821

    class OddModel(Model):
        def __init__(self, scenario: Odd = Odd):
            super().__init__(scenario=scenario)

    assert [p.kind for p in params.parameters_of(OddModel)] == [params.INT]


def test_config_round_trip(monkeypatch):
    """The config travels through JSON and the environment."""
    config = StudioConfig(target="model.py:M", seed=3, memory_budget_mib=2)
    assert StudioConfig.from_json(config.to_json()) == config
    assert config.memory_budget == 2 * 2**20
    assert config.source_file.name == "model.py"
    assert StudioConfig(target="pkg.mod:M").source_file is None
    monkeypatch.delenv("MODELLY_STUDIO_CONFIG", raising=False)
    config.export()
    assert StudioConfig.from_environment() == config


def test_load_a_file_inside_a_package_by_its_dotted_name():
    """An example's model.py is imported as its package module, not a copy."""
    module = wolf_sheep_model
    path = module.__file__
    assert module_name(Path(path))[1] == module.__name__
    assert load_model_class(f"{path}:WolfSheep") is WolfSheep


def test_load_a_loose_file(tmp_path, monkeypatch):
    """A file outside any package is imported under its own name."""
    (tmp_path / "loose_model.py").write_text(
        "from modelly import Model\n\n\nclass Loose(Model):\n    pass\n\n\n"
        "def portray(agent):\n    return None\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "path", list(sys.path))
    cls = load_model_class(f"{tmp_path / 'loose_model.py'}:Loose")
    assert cls.__module__ == "loose_model"
    assert (
        load_portrayal(f"{tmp_path / 'loose_model.py'}:portray").__name__ == "portray"
    )
    monkeypatch.delitem(sys.modules, "loose_model")


@pytest.mark.parametrize(
    ("target", "message"),
    [
        ("no_colon", "expected path/to/file.py"),
        ("missing.py:M", "no such file"),
        ("modelly.no_such_module:M", "cannot import"),
        ("modelly.examples:__all__", "not a Model subclass"),
    ],
)
def test_bad_targets(target, message):
    """Bad targets raise TargetError with a reason."""
    with pytest.raises(TargetError, match=message):
        load_model_class(target)


def test_bad_portrayal():
    """A portrayal must be callable."""
    with pytest.raises(TargetError, match="not a function"):
        load_portrayal("modelly.examples:__all__")
