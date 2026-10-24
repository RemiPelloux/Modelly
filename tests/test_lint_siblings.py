"""Tests for MDL107 across files: Column attributes of agents imported from sibling modules."""

import ast
import textwrap

from modelly.lint import lint_paths, lint_source
from modelly.lint.siblings import SiblingColumns

AGENTS = """
from modelly import Agent, Column

raise SystemExit("the linter must never run this file")


class Animal(Agent):
    energy = Column(float, default=5.0)


class Sheep(Animal):
    pass


class Plain(Agent):
    energy = 5.0
"""

MODEL = """
from modelly import Model
{imports}


class Pasture(Model):
    def step(self):
        for sheep in self.agents_by_type[{agent}]:
            sheep.energy -= 1
"""


def write_model(folder, imports, agent="Sheep", name="model.py"):
    """A model file in ``folder`` whose step loop writes ``energy`` one agent at a time."""
    path = folder / name
    path.write_text(
        textwrap.dedent(MODEL.format(imports=imports, agent=agent)), encoding="utf-8"
    )
    return path


def package(tmp_path, name="pkg"):
    """A package holding the agents module, with an empty ``__init__``."""
    folder = tmp_path / name
    folder.mkdir()
    (folder / "__init__.py").write_text("", encoding="utf-8")
    (folder / "agents.py").write_text(textwrap.dedent(AGENTS), encoding="utf-8")
    return folder


def codes(paths):
    """The rule codes ``lint_paths`` finds."""
    return [finding.rule.code for finding in lint_paths(paths)]


def test_relative_import_is_resolved(tmp_path):
    """``from .agents import Sheep`` reads the inherited Column from the sibling file."""
    write_model(package(tmp_path), "from .agents import Sheep")
    assert codes([tmp_path]) == ["MDL107"]


def test_absolute_import_within_the_tree(tmp_path):
    """``from pkg.agents import Sheep`` is found under the lint root."""
    write_model(package(tmp_path), "from pkg.agents import Sheep")
    assert codes([tmp_path]) == ["MDL107"]


def test_script_style_import_of_a_single_file(tmp_path):
    """Linting one file resolves ``from agents import Sheep`` next to it."""
    folder = package(tmp_path)
    model = write_model(folder, "from agents import Sheep")
    assert codes([model]) == ["MDL107"]


def test_plain_attributes_are_not_columns(tmp_path):
    """An imported class whose ``energy`` is a plain attribute gives no MDL107."""
    write_model(package(tmp_path), "from .agents import Plain", agent="Plain")
    assert codes([tmp_path]) == []


def test_imports_outside_the_lint_root_are_not_read(tmp_path):
    """An absolute import of a folder above the lint root is left alone."""
    package(tmp_path, "other")
    inner = tmp_path / "app"
    inner.mkdir()
    write_model(inner, "from other.agents import Sheep")
    assert codes([inner]) == []


def test_lint_source_without_siblings_sees_only_its_own_file(tmp_path):
    """The single-source API keeps its behaviour: no imported columns."""
    model = write_model(package(tmp_path), "from .agents import Sheep")
    assert lint_source(model.read_text(encoding="utf-8"), str(model)) == []


def test_each_imported_module_is_parsed_once(tmp_path):
    """Two modules importing the same agents file share one parse."""
    folder = package(tmp_path)
    first = write_model(folder, "from .agents import Sheep")
    second = write_model(folder, "from .agents import Sheep", name="other.py")
    siblings = SiblingColumns([tmp_path])
    assert siblings.imported(ast.parse(first.read_text(encoding="utf-8")), first) == {
        "energy"
    }
    (folder / "agents.py").write_text("", encoding="utf-8")
    assert siblings.imported(ast.parse(second.read_text(encoding="utf-8")), second) == {
        "energy"
    }
    assert list(siblings.parsed) == [(folder / "agents.py").resolve()]


def test_unparsable_sibling_adds_no_columns(tmp_path):
    """A sibling with a syntax error is skipped by the resolver."""
    folder = package(tmp_path)
    (folder / "agents.py").write_text("class Sheep(:\n", encoding="utf-8")
    model = write_model(folder, "from .agents import Sheep")
    siblings = SiblingColumns([tmp_path])
    assert (
        siblings.imported(ast.parse(model.read_text(encoding="utf-8")), model) == set()
    )
