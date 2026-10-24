"""Tests for TOML experiment specs."""

import textwrap

import pytest

from modelly.experiments import Range, designs
from modelly.experiments.spec import SpecError, load_spec

SPEC = """
[experiment]
model = "tests.experiments.models:Walk"
steps = 3
replicates = 2
seed = 5
outputs = ["mean"]
store = "runs/walk"
retries = 1

[space]
drift = { min = 0.0, max = 1.0 }
n = { min = 2, max = 6, integer = true }
policy = ["a", "b"]
fail = false

[design]
kind = "latin_hypercube"
n = 4

[run]
executor = "threads"
max_parallel = 2
[run.options]
"""


def write(tmp_path, text, name="study.toml"):
    """Write a spec file and return its path."""
    path = tmp_path / name
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def test_a_full_spec(tmp_path):
    """Every table maps to the Experiment and its run settings."""
    experiment, settings = load_spec(write(tmp_path, SPEC))
    assert experiment.space.parameters["drift"] == Range(0.0, 1.0)
    assert experiment.space.parameters["n"] == Range(2, 6, integer=True)
    assert experiment.space.fixed == {"fail": False}
    assert experiment.design == designs.latin_hypercube(4)
    assert (experiment.steps, experiment.replicates, experiment.seed) == (3, 2, 5)
    assert experiment.retries == 1
    assert experiment.store.path == (tmp_path / "runs" / "walk").resolve()
    assert (settings.executor, settings.max_parallel, settings.options) == (
        "threads",
        2,
        {},
    )


def test_model_file_relative_to_the_spec(tmp_path):
    """A .py model path is read from the spec's folder; custom points are kept."""
    (tmp_path / "counter.py").write_text(
        "from modelly import Model\n\n\nclass Counter(Model):\n    count = 0\n",
        encoding="utf-8",
    )
    spec = """
    [experiment]
    model = "counter.py:Counter"
    outputs = ["count"]
    [design]
    kind = "custom"
    points = [{}, {}]
    """
    experiment, settings = load_spec(write(tmp_path, spec))
    assert experiment.model == f"{(tmp_path / 'counter.py').resolve()}:Counter"
    assert len(experiment.points) == 2 and settings.executor == "processes"
    sobol = load_spec(
        write(
            tmp_path,
            spec.replace('"custom"', '"sobol"').replace("points = [{}, {}]", "n = 2"),
        )
    )
    assert sobol[0].design == designs.sobol(2)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (('model = "tests.experiments.models:Walk"', ""), "needs model"),
        (('model = "tests.experiments.models:Walk"', 'model = "Walk"'), "module:Class"),
        (("max = 1.0 }", "top = 1.0 }"), "a range is"),
        (('kind = "latin_hypercube"', 'kind = "random"'), "design.kind"),
        (("n = 4", "levels = 4"), "takes 'n'"),
    ],
)
def test_spec_errors(tmp_path, change, message):
    """Missing or malformed values name what is wrong."""
    with pytest.raises(SpecError, match=message):
        load_spec(write(tmp_path, SPEC.replace(*change)))
