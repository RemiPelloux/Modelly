"""Tests for the Mesa to Modelly codemod."""

from pathlib import Path

import pytest

from modelly import migrate

MESA2_MODEL = """import mesa
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector


class Sheep(mesa.Agent):
    def __init__(self, unique_id, model, energy):
        super().__init__(unique_id, model)
        self.energy = energy

    def step(self):
        self.model.grid.move_to_empty(self)
        x, y = self.pos


class Farm(mesa.Model):
    def __init__(self, n, seed=None):
        super().__init__(seed=seed)
        self.schedule = RandomActivation(self)
        self.grid = MultiGrid(10, 10, True)
        for i in range(n):
            sheep = Sheep(self.next_id(), self, 4)
            self.schedule.add(sheep)
        self.datacollector = DataCollector(model_reporters={"n": lambda m: m.schedule.get_agent_count()})

    def step(self):
        self.schedule.step()
        self.datacollector.collect(self)
        if self.schedule.steps > 10:
            self.running = False
"""

MESA3_MODEL = """from mesa import Agent, Model
from mesa.discrete_space import CellAgent, OrthogonalMooreGrid
from mesa.experimental.cell_space import Cell
import mesa.visualization as viz


class Walker(CellAgent):
    def __init__(self, model):
        super().__init__(model)
"""


def test_imports_are_mapped():
    """Mesa modules map to their Modelly counterparts, longest prefix first."""
    assert migrate.map_module("mesa") == "modelly"
    assert migrate.map_module("mesa.discrete_space") == "modelly.space"
    assert migrate.map_module("mesa.experimental.cell_space") == "modelly.space"
    assert migrate.map_module("mesa.space") == "modelly.space"
    assert migrate.map_module("mesa.batchrunner") == "modelly.scenarios"
    assert (
        migrate.map_module("mesa.visualization.components") == "modelly.viz.components"
    )
    assert migrate.map_module("mesaboard") == "mesaboard"


def test_mesa3_model_needs_only_imports():
    """A Mesa 3 model is fully migrated by the import rewrite."""
    result = migrate.migrate_source(Path("walker.py"), MESA3_MODEL)
    assert "from modelly import Agent, Model" in result.migrated
    assert "from modelly.space import CellAgent, OrthogonalMooreGrid" in result.migrated
    assert "from modelly.space import Cell" in result.migrated
    assert "import modelly.viz as viz" in result.migrated
    assert "mesa" not in result.migrated
    assert result.findings == []


def test_mesa2_model_rewrites_and_flags():
    """A Mesa 2 model gets the mechanical rewrites and a report for the rest."""
    result = migrate.migrate_source(Path("farm.py"), MESA2_MODEL)
    migrated = result.migrated
    assert "class Sheep(modelly.Agent):" in migrated
    assert "super().__init__(model)" in migrated
    assert 'self.agents.shuffle_do("step")' in migrated
    assert "if self.time > 10:" in migrated
    assert "lambda m: len(m.agents)" in migrated
    assert "from modelly.space import MultiGrid" in migrated

    reasons = {finding.reason.split(":")[0] for finding in result.findings}
    assert {
        "scheduler class",
        "schedule.add/remove",
        "legacy grid",
        "legacy grid call",
        "agent.pos",
        "unique_id parameter",
        "next_id()",
        "seed=",
    } <= reasons
    sections = {finding.section for finding in result.findings}
    assert {
        "activation-and-schedulers",
        "grids-and-positions",
        "agents",
        "model",
    } <= sections
    assert all(finding.line > 0 for finding in result.findings)


def test_seed_flag_ignores_plain_assignments():
    """``seed=`` keyword arguments are flagged, ``seed = ...`` assignments are not."""
    result = migrate.migrate_source(
        Path("x.py"), "seed = 3 * rep\nm = Farm(5, seed=seed)\n"
    )
    assert [finding.line for finding in result.findings] == [2]


def test_dry_run_leaves_files_alone_and_write_applies(tmp_path):
    """Without --write files are untouched; with it they are rewritten."""
    target = tmp_path / "pkg"
    target.mkdir()
    (target / "farm.py").write_text(MESA2_MODEL, encoding="utf-8")
    (target / "notes.txt").write_text("import mesa\n", encoding="utf-8")

    assert migrate.main([str(target)]) == 0
    assert (target / "farm.py").read_text(encoding="utf-8") == MESA2_MODEL

    assert migrate.main([str(target), "--write"]) == 0
    rewritten = (target / "farm.py").read_text(encoding="utf-8")
    assert "import modelly" in rewritten and "import mesa" not in rewritten
    assert (target / "notes.txt").read_text(encoding="utf-8") == "import mesa\n"


def test_report_mentions_guide_sections(capsys, tmp_path):
    """The report points every finding at a section of the migration guide."""
    (tmp_path / "farm.py").write_text(MESA2_MODEL, encoding="utf-8")
    migrate.main([str(tmp_path)])
    out = capsys.readouterr().out
    assert "Migration report: 1 file(s), 1 rewritten" in out
    assert f"see {migrate.GUIDE}#activation-and-schedulers" in out
    assert "+import modelly" in out  # the diff is printed on a dry run


def test_help_and_missing_path(capsys):
    """--help shows examples and exit codes; a missing file is a usage error."""
    with pytest.raises(SystemExit):
        migrate.main(["--help"])
    out = capsys.readouterr().out
    assert "examples:" in out and "exit status:" in out
    assert migrate.main(["does_not_exist.py"]) == migrate.EXIT_USAGE
    assert "modelly.migrate" in capsys.readouterr().err


MESA35_IMPORTS = """import mesa
from mesa.experimental.scenarios import Scenario
from mesa.experimental.data_collection import DataRecorder
from mesa.discrete_space.property_layer import PropertyLayer


class Citizen(mesa.discrete_space.CellAgent):
    pass
"""


def test_mesa35_experimental_modules_map_to_modelly_modules():
    """Scenarios, recorders and dotted ``mesa.discrete_space`` names reach real modules."""
    result = migrate.migrate_source(Path("model.py"), MESA35_IMPORTS)
    assert "from modelly.scenarios import Scenario" in result.migrated
    assert "from modelly.data.recorders import DataRecorder" in result.migrated
    assert "class Citizen(modelly.space.CellAgent):" in result.migrated


def test_a_module_modelly_lacks_is_reported_not_silently_rewritten():
    """The property-layer import, which Modelly has no module for, is flagged."""
    result = migrate.migrate_source(Path("model.py"), MESA35_IMPORTS)
    flagged = [f.line for f in result.findings if "no Modelly equivalent" in f.reason]
    assert flagged == [4]
