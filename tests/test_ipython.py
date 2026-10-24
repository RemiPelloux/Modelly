"""Tests for the Jupyter integration: the %modelly magics and the rich display of a Model."""

import pytest

from modelly import Agent, Model
from modelly.core import display
from modelly.ipython import notebook_class, run_magic, split
from modelly.scenarios import Scenario

BAD_MODEL = "import random\nfrom modelly import Agent\nclass A(Agent):\n    def step(self):\n        x = random.random()\n"


class Sheep(Agent):
    """A test agent."""


class Wolf(Agent):
    """Another test agent."""


class Pasture(Scenario):
    """A test scenario with a long parameter."""

    n: int = 3
    label: str = "x" * 100


class Field(Model):
    """A model with two agent classes."""

    def __init__(self, scenario=Pasture, rng=None):
        """Three sheep and one wolf."""
        super().__init__(
            scenario=scenario(rng=rng) if isinstance(scenario, type) else scenario
        )
        Sheep.create_agents(self, self.scenario.n)
        Wolf.create_agents(self, 1)

    def step(self):
        """Every agent acts."""
        self.agents.do("step")


def test_split_keeps_windows_paths_and_quotes():
    """Backslashes stay, quotes group a path with spaces."""
    assert split(r'lint C:\models\m.py "my dir\a.py"') == [
        "lint",
        r"C:\models\m.py",
        r"my dir\a.py",
    ]


def test_lint_magic(tmp_path, capsys):
    """%modelly lint prints the findings and returns the command's status."""
    path = tmp_path / "model.py"
    path.write_text(BAD_MODEL, encoding="utf-8")
    assert run_magic(f'lint "{path}"', {}) == 1
    assert "MDL001" in capsys.readouterr().out


def test_profile_magic_with_a_notebook_class(capsys):
    """A Model class of the notebook namespace is profiled by name."""
    assert notebook_class("Field", {"Field": Field}) is Field
    assert notebook_class("Field", {"Field": 3}) is None
    assert run_magic("profile Field --steps 3", {"Field": Field}) == 0
    out = capsys.readouterr().out
    assert "Field: 3 step(s) profiled" in out


def test_usage_and_help(capsys):
    """No command prints the usage; --help does not stop the kernel."""
    assert run_magic("", {}) is None
    assert "%modelly profile TARGET" in capsys.readouterr().out
    assert run_magic("lint --help", {}) == 0
    assert "%modelly lint" in capsys.readouterr().out


def test_extension_registers_the_magic(tmp_path, capsys):
    """%load_ext modelly.ipython adds %modelly to a real IPython shell."""
    interactive = pytest.importorskip("IPython.core.interactiveshell")
    shell = interactive.InteractiveShell.instance()
    try:
        shell.run_line_magic("load_ext", "modelly.ipython")
        path = tmp_path / "model.py"
        path.write_text(BAD_MODEL, encoding="utf-8")
        shell.run_line_magic("modelly", f'lint "{path}"')
        assert "MDL001" in capsys.readouterr().out
    finally:
        interactive.InteractiveShell.clear_instance()


def test_rich_display():
    """The HTML and Markdown views name the class, the scenario, time and population."""
    model = Field(rng=7)
    model.step()
    markdown = model._repr_markdown_()
    assert markdown.startswith("**Field**")
    assert "Pasture(n=3, label='xxx" in markdown and "..." in markdown
    assert "4 (Sheep: 3, Wolf: 1)" in markdown and "**time**: 1.0" in markdown
    html = model._repr_html_()
    assert "<caption><b>Field</b></caption>" in html and "&#x27;" in html


def test_display_of_an_empty_model_and_many_parameters():
    """No agents and a long scenario stay short."""
    many = Scenario(rng=1, **{f"p{i}": i for i in range(display.MAX_PARAMS + 3)})
    text = display.parameters(type("M", (), {"scenario": many})())
    assert "... 3 more" in text
    assert "**agents**: 0" in Model(rng=1)._repr_markdown_()
