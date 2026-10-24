"""The zoo catalogue, ``copy_model`` and the ``modelly zoo`` command."""

import importlib.util
import re
import sys

import pytest

from modelly.__main__ import main as modelly_main
from modelly.scenarios.scenario import Scenario
from modelly.zoo import MODELS, copy_model, get, names
from modelly.zoo.__main__ import main
from modelly.zoo.measures import clusters, gini

REFERENCE = re.compile(r"\(\d{4}\)")


@pytest.mark.parametrize("entry", MODELS, ids=lambda entry: entry.name)
def test_every_entry_loads_with_a_docstring_and_a_scenario(entry):
    """Each entry imports, names a Model and a Scenario, and documents itself."""
    model, scenario = entry.load()
    assert issubclass(scenario, Scenario)
    assert hasattr(model, "step")
    assert hasattr(model, "run")
    assert "Validation" in entry.doc()
    assert entry.source.name == "model.py"


@pytest.mark.parametrize("entry", MODELS, ids=lambda entry: entry.name)
def test_every_entry_has_a_docs_page_and_a_test(entry):
    """The zoo promise: a validation test and a docs page per model."""
    root = entry.source.parents[3]
    assert (root / "tests" / "zoo" / f"test_{entry.name}.py").is_file()
    assert (root / "docs" / "zoo" / f"{entry.name}.md").is_file()


def test_names_are_unique_and_lookup_suggests():
    """Names are unique; an unknown name raises KeyError with a close match."""
    assert len(set(names())) == len(MODELS)
    with pytest.raises(KeyError, match="age_seir"):
        get("age_sier")


def test_list_and_info(capsys):
    """``list`` prints every model, ``info`` the parameters and the reference."""
    assert main(["list"]) == 0
    listing = capsys.readouterr().out
    assert all(name in listing for name in names())
    assert main(["info", "age_seir"]) == 0
    info = capsys.readouterr().out
    assert "beta = 0.035" in info
    assert REFERENCE.search(info)
    assert main(["list", "--field", "epidemiology"]) == 0
    assert "age_seir" in capsys.readouterr().out


def test_unknown_model_fails(capsys):
    """An unknown name exits 1 with a message on stderr."""
    assert main(["info", "nope"]) == 1
    assert "No zoo model" in capsys.readouterr().err


def test_umbrella_command_runs_zoo(capsys):
    """``modelly zoo list`` goes through the umbrella entry point."""
    assert modelly_main(["zoo", "list"]) == 0
    assert "age_seir" in capsys.readouterr().out


def test_copy_writes_a_runnable_model(tmp_path, monkeypatch):
    """The copied model.py imports and runs on its own; nothing is overwritten."""
    target = tmp_path / "my_epidemic"
    written = copy_model("age_seir", target)
    assert [path.name for path in written] == ["model.py", "README.md"]
    readme = (target / "README.md").read_text(encoding="utf-8")
    assert "from model import AgeSEIR, SEIRScenario" in readme
    spec = importlib.util.spec_from_file_location("copied_seir", target / "model.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "copied_seir", module)
    spec.loader.exec_module(module)
    model = module.AgeSEIR(module.SEIRScenario(rng=1, steps=5))
    model.run()
    assert model.time == 5
    with pytest.raises(FileExistsError):
        copy_model("age_seir", target)


def test_copy_command(tmp_path, capsys):
    """``modelly zoo copy`` reports the files and refuses to overwrite them."""
    assert main(["copy", "age_seir", str(tmp_path / "out")]) == 0
    assert "model.py" in capsys.readouterr().out
    assert main(["copy", "age_seir", str(tmp_path / "out")]) == 1
    assert "Not overwriting" in capsys.readouterr().err


def test_measures():
    """Gini of equal and concentrated values; clusters with and without a floor."""
    assert gini([2, 2, 2]) == 0.0
    assert gini([0, 0, 0, 4]) == pytest.approx(0.75)
    assert gini([]) == 0.0
    values = [0.1, 0.11, 0.5, 0.52, 0.9]
    assert clusters(values, 0.05) == 3
    assert clusters(values, 0.05, min_share=0.3) == 2
    assert clusters([], 0.05) == 0
