"""Tests for modelly.lint: each rule fires on its pattern and stays quiet on the fix."""

import json
import textwrap
from pathlib import Path

import pytest

from modelly.lint import RULES, lint_paths, lint_source
from modelly.lint.__main__ import main

HEADER = """
import copy
import os
import random
import time
import uuid
from datetime import datetime
import numpy as np
import pandas as pd
from modelly import Agent, Column, Model
"""
HEADER_LINES = HEADER.count("\n")


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
        "np.random.seed(3)",
        "g = np.random.default_rng(None)",
        "g = np.random.default_rng(seed=None)",
        "from numpy.random import default_rng\ng = default_rng()",
        "r = random.Random()",
        "r = random.SystemRandom(1)",
        "g = np.random.Generator(np.random.PCG64())",
        "import numpy.random as npr\nx = npr.uniform()",
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
    "MDL005": [
        "class M(Model):\n    def step(self):\n        self.t = time.time()",
        "class A(Agent):\n    def step(self):\n        self.born = datetime.now()",
        "class A(Agent):\n    def __init__(self, model):\n        super().__init__(model)\n        self.tag = uuid.uuid4()",
        "class A(Agent):\n    def step(self):\n        b = os.urandom(4)",
        "import secrets\nclass A(Agent):\n    def step(self):\n        b = secrets.token_hex()",
        "import datetime as dt\nclass M(Model):\n    def step(self):\n        d = dt.date.today()",
    ],
    "MDL006": [
        "class A(Agent):\n    def step(self):\n        self.group = hash(self.name) % 4",
        "order = sorted(agents, key=id)",
        "agents.sort(key=lambda a: id(a))",
        "first = min(agents, key=id)",
    ],
    "MDL007": [
        "class M(Model):\n    def step(self):\n        for a in self.agents:\n            a.prey.remove()",
        "class A(Agent):\n    def step(self):\n        for b in self.model.agents_by_type[A]:\n            if b.weak:\n                b.target.remove()",
    ],
    "MDL008": [
        "N = 0\nclass A(Agent):\n    def step(self):\n        global N\n        N += 1",
    ],
    "MDL009": [
        "class M(Model):\n    def step(self):\n        self.agents.remove(a)",
        "class A(Agent):\n    def die(self):\n        self.model.agents.discard(self)",
        "class M(Model):\n    def setup(self):\n        self.agents_by_type[A].add(a)",
    ],
    "MDL010": [
        "from modelly import run_batch\nrun_batch(lambda t: t, [1, 2])",
        "def main():\n    def run(t):\n        return t\n    run_batch(run, tasks)",
        "def main():\n    class M(Model):\n        pass\n    RunConfiguration(M, until=3)",
        "def main():\n    def run(t):\n        return t\n    run_grid(functools.partial(run, 1), grid)",
        "Experiment(model_factory=lambda s: M(s), reporters={'n': lambda m: len(m.agents)})",
        "run_batch(go, tasks, workers=[lambda: 1])",
        "sweep(model_factory=lambda s: M(s))",
    ],
    "MDL012": [
        "import requests\nclass A(Agent):\n    def step(self):\n        r = requests.post(URL, json={})",
        "from urllib.request import urlopen\nclass M(Model):\n    def step(self):\n        urlopen(URL)",
        "import openai\nclass A(Agent):\n    def step(self):\n        c = openai.OpenAI()",
        "class A(Agent):\n    def step(self):\n        r = self.client.chat.completions.create(model=M)",
        "class A(Agent):\n    def step(self):\n        r = CLIENT.messages.create(model=M, messages=[])",
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
    "MDL106": [
        "class M(Model):\n    def step(self):\n        df = pd.DataFrame(self.rows)",
        "class M(Model):\n    def step(self):\n        self.log = pd.concat([self.log, row])",
    ],
    "MDL107": [
        "class A(Agent):\n    wealth = Column(int)\nclass M(Model):\n    def step(self):\n        for a in self.agents:\n            a.wealth += 1",
        "class A(Agent):\n    e: float = Column(float)\nclass M(Model):\n    def step(self):\n        for a in self.agents:\n            if a.e > 0:\n                a.e -= 0.5",
    ],
    "MDL105": [
        "class A(Agent):\n    def step(self):\n"
        + "".join(f"        if self.x == {i}:\n            pass\n" for i in range(13))
    ],
}

GOOD = [
    "def run(t):\n    return t\nrun_batch(run, [1, 2])",
    "run_batch(lambda t: t, [1, 2], workers=1)",
    "def main():\n    run_grid(functools.partial(run, 1), grid)",
    "class M(Model):\n    pass\ndef main():\n    RunConfiguration(M, until=3)",
    "p = self.model.agents.select(lambda a: a.x)",
    "def main():\n    def key(a):\n        return a.x\n    agents.sort(key=key)",
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
    "g = np.random.default_rng(seed=7)",
    "g = np.random.Generator(np.random.PCG64(7))",
    "from numpy.random import Generator, PCG64",
    "class A(Agent):\n    def step(self):\n        self.g = self.random.random()",
    "start = time.time()",
    "class A(Agent):\n    __slots__ = ['x', 'y']",
    "from typing import ClassVar\nclass A(Agent):\n    MAP: ClassVar[dict] = {}",
    "class A(Agent):\n    def step(self):\n        t0 = time.perf_counter()",
    "class A(Agent):\n    def __hash__(self):\n        return hash(self.unique_id)",
    "order = sorted(agents, key=lambda a: a.unique_id)",
    "h = hash('a')",
    "class M(Model):\n    def step(self):\n        for a in self.agents:\n            if a.energy < 0:\n                a.remove()",
    "class M(Model):\n    def step(self):\n        for a in self.agents:\n            a.items.remove(x)",
    "class M(Model):\n    def step(self):\n        for c in self.cells:\n            c.agent.remove()",
    "N = 0\ndef bump():\n    global N\n    N += 1",
    "class M(Model):\n    def step(self):\n        self.agents.select(lambda a: a.x).remove(a)",
    "class A(Agent):\n    def step(self):\n        self.cell.agents.remove(self)",
    "class M(Model):\n    def report(self):\n        return pd.DataFrame(self.rows)",
    "class A(Agent):\n    wealth = Column(int)\nclass M(Model):\n    def step(self):\n        for a in self.agents:\n            a.wealth += self.random.random()",
    "class A(Agent):\n    wealth = Column(int)\nclass M(Model):\n    def step(self):\n        for a in self.agents:\n            a.wealth += 1\n            a.move()",
    "class M(Model):\n    def step(self):\n        for a in self.agents:\n            a.plain += 1",
    "import requests\ndef fetch_data():\n    return requests.get(URL)",
    "class A(Agent):\n    def step(self):\n        self.vote = self.decide(prompt, schema)",
    "class M(Model):\n    def step(self):\n        r = self.llm.complete('hi')",
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
    path.write_text(HEADER + textwrap.dedent(body), encoding="utf-8")
    return path


def test_cli_exit_status_and_text(tmp_path, capsys):
    """Findings exit 1 and print ``path:line:col: CODE``; --exit-zero exits 0."""
    path = write(tmp_path, "x = random.random()")
    assert main([str(path)]) == 1
    out = capsys.readouterr().out
    assert (
        f"{path}:{HEADER_LINES + 1}:5: MDL001" in out
        and "1 finding(s): 1 error(s), 0 warning(s)" in out
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
    path.write_text("def (:\n", encoding="utf-8")
    assert main([str(path)]) == 2
    assert "modelly.lint" in capsys.readouterr().err
