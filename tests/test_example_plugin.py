"""The example third-party plugin (examples/plugins), installed, in every group.

The plugin's folder goes on ``sys.path`` with a ``dist-info`` written from its
``pyproject.toml`` entry points, which is an installed distribution as far as
``importlib.metadata`` is concerned. Each test then uses one entry point the way
Modelly does: the sampler through an experiment file, the executor by name, the
lint rule through ``lint_source``, the Studio view as a tab; spaces and collectors
are loaded with ``discover`` and used in a model.
"""

import sys
import textwrap
import tomllib
from pathlib import Path

import pytest

from modelly import Agent, Model
from modelly.data.collector import DataCollector
from modelly.experiments import Experiment, ScenarioSpace
from modelly.experiments.designs import design_factory, design_kinds
from modelly.experiments.executors import available_executors, get_executor
from modelly.experiments.spec import load_spec
from modelly.lint import lint_source
from modelly.lint.plugins import plugin_rules
from modelly.lint.report import list_rules, statistics
from modelly.plugins import GROUPS, discover

PLUGIN = Path(__file__).resolve().parents[1] / "examples" / "plugins"
PLUGIN = PLUGIN / "modelly-example-plugin"
PACKAGE = "modelly_example_plugin"
CELLS = 12
WALKERS = 6
STEPS = 3


def _write_dist_info(site: Path) -> None:
    """A dist-info for the example plugin, its entry points read from pyproject.toml."""
    project = tomllib.loads((PLUGIN / "pyproject.toml").read_text(encoding="utf-8"))
    info = site / "modelly_example_plugin-1.0.0.dist-info"
    info.mkdir()
    name = project["project"]["name"]
    (info / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0.0\n", encoding="utf-8"
    )
    lines = []
    for group, points in project["project"]["entry-points"].items():
        lines.append(f"[{group}]")
        lines += [f"{key} = {value}" for key, value in points.items()]
    (info / "entry_points.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def installed(tmp_path, monkeypatch):
    """The example plugin installed for the duration of a test."""
    _write_dist_info(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.syspath_prepend(str(PLUGIN))
    plugin_rules.cache_clear()
    yield
    plugin_rules.cache_clear()
    for module in [m for m in sys.modules if m.split(".")[0] == PACKAGE]:
        del sys.modules[module]


class Walker(Agent):
    """An agent stepping to a random neighbour of its cell on the ring."""

    def __init__(self, model, cell):
        """A walker on ``cell``."""
        super().__init__(model)
        self.cell = cell
        self.moved = False

    def step(self):
        """Move to a random neighbouring cell."""
        self.cell = self.cell.neighborhood.select_random_cell()
        self.moved = True


class RingWalk(Model):
    """Walkers on the plugin's ring, counted with the plugin's reporter."""

    def __init__(self, space_class, share_of, rng=None):
        """``WALKERS`` walkers on a ring of ``CELLS`` cells."""
        super().__init__(rng=rng)
        self.space = space_class(CELLS, random=self.random)
        for _ in range(WALKERS):
            Walker(self, self.space.select_random_empty_cell())
        self.datacollector = DataCollector({"moved": share_of("moved", True)})

    def step(self):
        """Every walker moves; then collect."""
        self.agents.shuffle_do("step")
        self.datacollector.collect(self)


def test_the_plugin_declares_every_group(installed):
    """One entry point in each group Modelly defines."""
    assert all(discover(group) for group in GROUPS)


def test_space_and_collector_run_in_a_model(installed):
    """The ring space and the share reporter, loaded from their entry points."""
    ring = discover("modelly.spaces")["ring"].load()
    share_of = discover("modelly.collectors")["share_of"].load()
    model = RingWalk(ring, share_of, rng=3)
    model.run_for(STEPS)
    assert len(model.space.all_cells) == CELLS
    assert all(len(cell.neighborhood) == 2 for cell in model.space.all_cells)
    assert model.datacollector.get_model_vars_dataframe()["moved"].iloc[-1] == 1.0


def test_sampler_is_a_design_kind_of_experiment_files(installed, tmp_path):
    """``[design] kind = "uniform"`` reads the plugin's sampler."""
    assert "uniform" in design_kinds()
    spec = tmp_path / "study.toml"
    spec.write_text(
        textwrap.dedent(
            """
            [experiment]
            model = "tests.experiments.models:Walk"
            steps = 2
            outputs = ["mean"]
            store = "runs"
            [space]
            drift = { min = 0.0, max = 1.0 }
            [design]
            kind = "uniform"
            n = 5
            """
        ),
        encoding="utf-8",
    )
    experiment, _ = load_spec(spec)
    points = experiment.points
    assert len(points) == 5
    assert all(0.0 <= point["drift"] <= 1.0 for point in points)
    assert points == load_spec(spec)[0].points  # seeded by the experiment
    with pytest.raises(KeyError):
        design_factory("no_such_design")


def test_executor_runs_an_experiment_by_name(installed, tmp_path):
    """``executor="in_order"`` is the plugin's executor."""
    pytest.importorskip("pyarrow")
    from tests.experiments.models import Walk  # noqa: PLC0415

    assert "in_order" in available_executors()
    assert get_executor("in_order").name == "in_order"
    space = ScenarioSpace(drift=(0.0, 1.0), n=3)
    design = design_factory("uniform")(2)
    experiment = Experiment(
        Walk, space, design=design, steps=2, outputs="mean", store=tmp_path / "runs"
    )
    assert experiment.run("in_order").done == 2


def test_lint_rule_reports_its_code(installed):
    """``modelly lint`` runs the plugin's EXP001 next to the built-in rules."""
    source = "def step(self):\n    print(self)\n    print(1)  # noqa: EXP001\n"
    findings = lint_source(source, "model.py")
    assert [(f.rule.code, f.line) for f in findings] == [("EXP001", 2)]
    assert "EXP001" in list_rules()
    assert "EXP001" in statistics(findings)


def test_studio_shows_the_plugin_view_as_a_tab(installed):
    """``all_tabs`` ends with the plugin's view, named after its entry point."""
    pytest.importorskip("solara")
    from modelly.studio.app import TABS, all_tabs  # noqa: PLC0415

    all_tabs.cache_clear()
    tabs = all_tabs()
    all_tabs.cache_clear()
    assert tabs[: len(TABS)] == TABS
    assert [name for name, _ in tabs[len(TABS) :]] == ["Scenario"]
