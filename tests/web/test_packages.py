"""Tests for finding the Pyodide packages a model needs."""

import pytest

from modelly.web.packages import (
    CORE,
    ModelRunError,
    distributions_of,
    needed_packages,
    normalise,
)

SEED = 1
STEPS = 2


def test_normalise_spells_names_like_the_lock_file():
    """PEP 503 names: lower case, runs of - _ . become one dash."""
    assert normalise("Python_Dateutil") == "python-dateutil"
    assert normalise("zope.interface") == "zope-interface"


def test_stdlib_and_modelly_are_not_packages():
    """Only third-party distributions count."""
    assert distributions_of({"numpy", "json", "modelly", "no_such_module"}) == {"numpy"}


def test_one_example_needs_only_the_core():
    """Importing one example no longer imports the others (networkx)."""
    target = "modelly.examples.basic.schelling.model:Schelling"
    assert needed_packages(target, STEPS, SEED) == sorted(CORE)


def test_lazy_imports_are_seen_when_the_model_runs():
    """The network example needs networkx and scipy, not matplotlib."""
    target = "modelly.examples.basic.virus_on_network.model:VirusOnNetwork"
    found = needed_packages(target, STEPS, SEED)
    assert {"networkx", "scipy", *CORE} <= set(found)
    assert "matplotlib" not in found


def test_a_model_file_that_fails_is_a_run_error(tmp_path):
    """A model raising in its step is reported with its traceback."""
    path = tmp_path / "broken.py"
    path.write_text(
        "from modelly import Model\n\n\n"
        "class Broken(Model):\n"
        "    def step(self):\n"
        "        raise RuntimeError('boom')\n",
        encoding="utf-8",
    )
    with pytest.raises(ModelRunError, match="boom"):
        needed_packages(f"{path}:Broken", STEPS, SEED)
