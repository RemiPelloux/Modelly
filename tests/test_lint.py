"""Tests for modelly.lint: each rule fires on its pattern and stays quiet on the fix."""

import json
import textwrap
from pathlib import Path

import pytest

from modelly.lint import RULES, lint_paths, lint_source
from modelly.lint.__main__ import main

HEADER = """
import copy
import random
import numpy as np
from modelly import Agent, Model
"""


def codes(body: str) -> list[str]:
    """The rule codes found in ``body``, below the shared imports."""
    return [f.rule.code for f in lint_source(HEADER + textwrap.dedent(body))]


BAD = {
    "MDL001": [
        "x = random.random()",
        "x = np.random.normal()",
        "g = np.random.default_rng()",
        "from random import choice\nx = choice([1, 2])",
        "p = [x for b in items for x in random.sample(b, 1)]",
    ],
    "MDL002": [
        "class A(Agent):\n    def __init__(self, model):\n        self.x = 1",
        "class M(Model):\n    def __init__(self):\n        self.n = 3",
        "class A(Agent):\n    pass\nclass B(A):\n    def __init__(self, model):\n        self.x = 1",
    ],
    "MDL003": [
        "for a in set(items):\n    pass",
        "ids = [a.unique_id for a in {x, y}]",
    ],
    "MDL004": [
        "class A(Agent):\n    friends = []",
        "class A(Agent):\n    seen: dict = {}",
    ],
    "MDL101": [
        "class A(Agent):\n    def step(self):\n        for a in self.model.agents:\n            pass",
        "class A(Agent):\n    def step(self):\n        r = [a for a in self.model.agents_by_type[A]]",
        "class A(Agent):\n    def step(self):\n        p = self.model.agents.select(lambda a: a.x)",
    ],
    "MDL102": [
        "class M(Model):\n    def step(self):\n        for a in self.agents:\n            for b in self.agents:\n                pass",
        "class M(Model):\n    def step(self):\n        p = [(a, b) for a in self.agents for b in self.agents]",
    ],
    "MDL103": [
        "class M(Model):\n    def step(self):\n        for a in self.agents:\n            a.step()"
    ],
    "MDL104": [
        "class A(Agent):\n    def step(self):\n        s = copy.deepcopy(self.x)"
    ],
    "MDL105": [
        "class A(Agent):\n    def step(self):\n"
        + "".join(f"        if self.x == {i}:\n            pass\n" for i in range(13))
    ],
}

GOOD = [
    "x = self.random.random()",
    "g = np.random.default_rng(42)",
    "r = random.Random(42)",
    "class A(Agent):\n    def __init__(self, model):\n        super().__init__(model)",
    "class Helper:\n    def __init__(self):\n        self.x = 1",
    "for a in sorted(set(items)):\n    pass",
    "class A(Agent):\n    size = 3\n    name = 'a'",
    "class A(Agent):\n    def step(self):\n        for a in self.cell.agents:\n            pass",
    "class A(Agent):\n    def step(self):\n        n = self.cell.neighborhood.agents",
    'class M(Model):\n    def step(self):\n        self.agents.shuffle_do("step")',
    "class M(Model):\n    def step(self):\n        rich = [a for a in self.agents if a.wealth > 1]",
    "class M(Model):\n    def step(self):\n        for a in self.agents:\n            a.step()\n            a.grow()",
    "class A(Agent):\n    def step(self):\n        if self.x:\n            pass",
]


@pytest.mark.parametrize(
    ("code", "source"), [(c, s) for c, sources in BAD.items() for s in sources]
)
def test_rule_fires(code, source):
    """Each bad pattern is reported with its rule."""
    assert code in codes(source)


@pytest.mark.parametrize("source", GOOD)
def test_fix_is_quiet(source):
    """The recommended form of each pattern is not reported."""
    assert codes(source) == []


def test_every_rule_has_a_bad_example():
    """No rule ships without a test that makes it fire."""
    assert set(BAD) == set(RULES)


def test_noqa_with_and_without_codes():
    """``# noqa`` silences a line; ``# noqa: CODE`` only that code."""
    assert codes("x = random.random()  # noqa") == []
    assert codes("x = random.random()  # noqa: MDL001") == []
    assert codes("x = random.random()  # noqa: MDL101") == ["MDL001"]


def test_shipped_examples_are_clean():
    """The examples are the models people copy, so they pass every rule."""
    examples = Path(__file__).parents[1] / "modelly" / "examples"
    assert lint_paths([examples]) == []


def write(tmp_path: Path, body: str) -> Path:
    """Write a model file and return its path."""
    path = tmp_path / "model.py"
    path.write_text(HEADER + textwrap.dedent(body))
    return path


def test_cli_exit_status_and_text(tmp_path, capsys):
    """Findings exit 1 and print ``path:line:col: CODE``; --exit-zero exits 0."""
    path = write(tmp_path, "x = random.random()")
    assert main([str(path)]) == 1
    out = capsys.readouterr().out
    assert (
        f"{path}:6:5: MDL001" in out and "1 finding(s): 1 error(s), 0 warning(s)" in out
    )
    assert main([str(path), "--exit-zero"]) == 0


def test_cli_select_ignore_and_json(tmp_path, capsys):
    """--select and --ignore filter by prefix; --format json is machine readable."""
    path = write(tmp_path, "x = random.random()\nfor a in set(b):\n    pass")
    assert main([str(path), "--ignore", "MDL0"]) == 0
    capsys.readouterr()
    main([str(path), "--select", "MDL003", "--format", "json"])
    found = json.loads(capsys.readouterr().out)
    assert [f["rule"]["code"] for f in found] == ["MDL003"]


def test_cli_clean_file_and_list_rules(tmp_path, capsys):
    """A clean file exits 0; --list-rules prints every code."""
    assert main([str(write(tmp_path, "x = 1"))]) == 0
    assert main(["--list-rules"]) == 0
    out = capsys.readouterr().out
    assert all(code in out for code in RULES)


def test_cli_syntax_error_exits_2(tmp_path, capsys):
    """A file that does not parse is a usage error, not a finding."""
    path = tmp_path / "broken.py"
    path.write_text("def (:\n")
    assert main([str(path)]) == 2
    assert "modelly.lint" in capsys.readouterr().err
