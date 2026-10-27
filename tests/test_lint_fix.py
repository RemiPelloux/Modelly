"""Tests for ``modelly lint --fix`` and ``--diff``: each fix, idempotence, noqa, the CLI."""

import textwrap

import pytest

from modelly.lint import lint_source
from modelly.lint.__main__ import EXIT_CLEAN, EXIT_FINDINGS, main
from modelly.lint.fix import fix_source

HEADER = "import random\nimport numpy as np\nfrom modelly import Agent, Model\n"

# (before, after): the body below HEADER, dedented.
FIXES = {
    "stdlib draw in an agent": (
        """
        class A(Agent):
            def step(self):
                if random.random() < 0.5:  # keep this comment
                    self.x = random.choice([1, 2])
        """,
        """
        class A(Agent):
            def step(self):
                if self.random.random() < 0.5:  # keep this comment
                    self.x = self.random.choice([1, 2])
        """,
    ),
    "numpy draw in a model": (
        """
        class M(Model):
            def step(self):
                noise = np.random.normal(0, 1, size=3)
        """,
        """
        class M(Model):
            def step(self):
                noise = self.rng.normal(0, 1, size=3)
        """,
    ),
    "imported name": (
        """
        from random import shuffle
        class A(Agent):
            def step(self):
                shuffle(self.items)
        """,
        """
        from random import shuffle
        class A(Agent):
            def step(self):
                self.random.shuffle(self.items)
        """,
    ),
    "agent super call after the docstring": (
        '''
        class A(Agent):
            def __init__(self, model, size):
                """Docs."""
                self.size = size
        ''',
        '''
        class A(Agent):
            def __init__(self, model, size):
                """Docs."""
                super().__init__(model)
                self.size = size
        ''',
    ),
    "model super call with the scenario": (
        """
        class M(Model):
            def __init__(self, scenario=None):
                self.n = 3
        """,
        """
        class M(Model):
            def __init__(self, scenario=None):
                super().__init__(scenario=scenario)
                self.n = 3
        """,
    ),
    "loop over a set": (
        """
        for x in set(names):
            print(x)
        ids = [a.unique_id for a in set(self.cell.agents)]
        """,
        """
        for x in sorted(set(names)):
            print(x)
        ids = [a.unique_id for a in sorted(set(self.cell.agents), key=lambda a: a.unique_id)]
        """,
    ),
    "registry edits": (
        """
        class A(Agent):
            def die(self):
                self.model.agents.discard(self)
        class M(Model):
            def reset(self):
                self.agents.clear()
        """,
        """
        class A(Agent):
            def die(self):
                self.remove()
        class M(Model):
            def reset(self):
                self.agents.do("remove")
        """,
    ),
    "nested fixes": (
        """
        class A(Agent):
            def step(self):
                for x in set(random.sample(self.items, 2)):
                    pass
        """,
        """
        class A(Agent):
            def step(self):
                for x in sorted(set(self.random.sample(self.items, 2))):
                    pass
        """,
    ),
    "samplers in a model method": (
        """
        from scipy.stats import norm, qmc
        class M(Model):
            def setup(self):
                units = qmc.LatinHypercube(d=2).random(8)
                halton = qmc.Halton(
                    3,
                    scramble=True,
                )
                empty = qmc.Sobol()
                noise = norm(0, 1).rvs(size=4, random_state=None)
        """,
        """
        from scipy.stats import norm, qmc
        class M(Model):
            def setup(self):
                units = qmc.LatinHypercube(d=2, rng=self.rng).random(8)
                halton = qmc.Halton(
                    3,
                    scramble=True, rng=self.rng,
                )
                empty = qmc.Sobol(rng=self.rng)
                noise = norm(0, 1).rvs(size=4, random_state=self.rng)
        """,
    ),
}

# Findings the fixer must leave alone: the rewrite would be a guess.
UNFIXED = [
    "from scipy.stats import qmc\nx = qmc.Sobol(2)",  # not in a method: no self.rng
    "from SALib.sample import saltelli\nclass M(Model):\n    def setup(self):\n        x = saltelli.sample(p, 8)",
    "x = random.random()",  # not in a method: there is no self.random
    "class A(Agent):\n    def step(self):\n        r = random.Random()",
    "class A(Agent):\n    def step(self):\n        x = np.random.randint(3)",
    "class B(Agent):\n    pass\nclass A(B):\n    def __init__(self, model):\n        self.x = 1",
    "class M(Model):\n    def __init__(self, rng, scenario):\n        self.x = 1",
    "class A(Agent):\n    def __init__(self, world):\n        self.x = 1",
    "class A(Agent):\n    def __init__(self, model): self.x = 1",
    "class A(Agent):\n    def step(self):\n        self.model.agents.add(self)",
]


def source(body: str) -> str:
    """The module: shared imports, then ``body``."""
    return HEADER + textwrap.dedent(body)


@pytest.mark.parametrize("name", FIXES)
def test_fix(name):
    """Each fix rewrites exactly its expression, keeping comments and layout."""
    before, after = FIXES[name]
    fixed, count = fix_source(source(before))
    assert fixed == source(after)
    assert count > 0


@pytest.mark.parametrize("name", FIXES)
def test_fix_is_idempotent(name):
    """A second run finds nothing to fix, and the fixed findings are gone."""
    fixed, _ = fix_source(source(FIXES[name][0]))
    assert fix_source(fixed) == (fixed, 0)
    codes = {f.rule.code for f in lint_source(fixed)}
    assert not codes & {"MDL001", "MDL002", "MDL003", "MDL009", "MDL011"}


@pytest.mark.parametrize("body", UNFIXED)
def test_ambiguous_findings_are_left(body):
    """No fix is applied when the right rewrite is not certain."""
    assert lint_source(source(body))
    assert fix_source(source(body)) == (source(body), 0)


def test_noqa_keeps_the_finding_and_its_fix_out():
    """A suppressed finding is not fixed; the one beside it is."""
    body = "class A(Agent):\n    def step(self):\n"
    body += "        a = random.random()  # noqa: MDL001\n        b = random.random()\n"
    fixed, count = fix_source(source(body))
    assert count == 1
    assert "a = random.random()  # noqa: MDL001" in fixed
    assert "b = self.random.random()" in fixed


def test_keep_filters_by_rule():
    """Only the findings ``keep`` accepts (select, ignore, per-file) are fixed."""
    body = "for x in set(s):\n    pass\nclass A(Agent):\n    def __init__(self, model):\n        self.x = 1\n"
    fixed, count = fix_source(source(body), keep=lambda f: f.rule.code == "MDL003")
    assert count == 1 and "sorted(set(s))" in fixed and "super()" not in fixed


def test_crlf_and_unicode_are_kept(tmp_path):
    """Line endings and non-ASCII text before the fix survive it."""
    path = tmp_path / "model.py"
    text = 'from modelly import Agent\nimport random\nclass A(Agent):\n    def step(self):\n        s = "é"; x = random.random()\n'
    path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert main(["--fix", str(path)]) == EXIT_CLEAN
    fixed = path.read_bytes().decode("utf-8")
    assert fixed == text.replace("\n", "\r\n").replace("x = random", "x = self.random")


def test_cli_diff_writes_nothing(tmp_path, capsys):
    """--diff prints a unified diff, exits 1, and leaves the file as it was."""
    path = tmp_path / "model.py"
    original = source("for x in set(s):\n    pass\n")
    path.write_text(original, encoding="utf-8")
    assert main(["--diff", str(path)]) == EXIT_FINDINGS
    out = capsys.readouterr().out
    assert "-for x in set(s):" in out and "+for x in sorted(set(s)):" in out
    assert path.read_text(encoding="utf-8") == original
    path.write_text(source("for x in sorted(s):\n    pass\n"), encoding="utf-8")
    assert main(["--diff", str(path)]) == EXIT_CLEAN


def test_cli_fix_reports_what_is_left(tmp_path, capsys):
    """--fix writes the fixes and reports the findings without one."""
    path = tmp_path / "model.py"
    body = "class A(Agent):\n    def step(self):\n        x = random.random()\n        global N\n"
    path.write_text(source(body), encoding="utf-8")
    assert main(["--fix", str(path)]) == EXIT_FINDINGS
    captured = capsys.readouterr()
    assert "MDL008" in captured.out and "MDL001" not in captured.out
    assert "1 fix(es) applied" in captured.err
    assert "self.random.random()" in path.read_text(encoding="utf-8")
