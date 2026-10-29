"""A numpy dataset's fields belong to each model: live models, loaded copies, fresh processes."""

import gc
import subprocess
import sys
import textwrap

from modelly.core.agent import Agent
from modelly.core.model import Model


class Walker(Agent):
    """An agent with one numpy-tracked field."""

    def __init__(self, model, value):
        """Start at value."""
        super().__init__(model)
        self.value = value


class Walkers(Model):
    """Walkers whose value is tracked in a numpy dataset."""

    def __init__(self, n=3, start=0.0, capacity=100):
        """Create n walkers valued start, start + 1, ..."""
        super().__init__(rng=1)
        self.data_registry.track_agents_numpy(
            Walker, "walkers", fields=["value"], n=capacity
        )
        Walker.create_agents(self, n, [start + i for i in range(n)])

    def values(self):
        """Every walker's value, in creation order."""
        return [float(agent.value) for agent in self.agents]


def test_two_live_models_keep_their_own_values():
    """The second model used to take over the first one's fields."""
    first = Walkers(start=0.0)
    second = Walkers(start=100.0)
    for agent in first.agents:
        agent.value += 0.5

    assert first.values() == [0.5, 1.5, 2.5]
    assert second.values() == [100.0, 101.0, 102.0]
    assert first.data_registry["walkers"].data[:, 0].tolist() == [0.5, 1.5, 2.5]


def test_growth_keeps_both_models_apart():
    """Growing one model's array past its capacity does not redirect the other."""
    first = Walkers(n=2, start=0.0, capacity=2)
    second = Walkers(n=2, start=50.0, capacity=2)
    Walker.create_agents(first, 300, [7.0] * 300)

    assert first.values()[:2] == [0.0, 1.0]
    assert len(first.data_registry["walkers"]) == 302
    assert second.values() == [50.0, 51.0]


def test_a_loaded_copy_reads_its_own_array(tmp_path):
    """Model.load used to give agents that read the original model's array."""
    model = Walkers()
    model.save(tmp_path / "walkers.ckpt")
    loaded = Model.load(tmp_path / "walkers.ckpt")
    for agent in model.agents:
        agent.value = -1.0

    assert loaded.values() == [0.0, 1.0, 2.0]
    assert model.values() == [-1.0, -1.0, -1.0]


def test_closing_one_model_leaves_the_other_working():
    """The fields leave the class only when the last open dataset of that name closes."""
    gc.collect()  # models of the earlier tests, never closed, are collected
    first, second = Walkers(start=0.0), Walkers(start=10.0)
    first.data_registry.close()
    assert second.values() == [10.0, 11.0, 12.0]

    second.data_registry.close()
    assert not isinstance(vars(Walker).get("value"), property)


MODULE = """
from modelly.core.agent import Agent
from modelly.core.model import Model


class Walker(Agent):
    def __init__(self, model, value):
        super().__init__(model)
        self.value = value


class Walkers(Model):
    def __init__(self):
        super().__init__(rng=1)
        self.data_registry.track_agents_numpy(Walker, "walkers", fields=["value"], n=2)
        Walker.create_agents(self, 5, [float(i) for i in range(5)])
"""


def test_a_checkpoint_resumes_in_a_fresh_process(tmp_path):
    """The class gets its fields back on load; 1.4.1 raised AttributeError there."""
    (tmp_path / "walkers_module.py").write_text(textwrap.dedent(MODULE))
    path = (tmp_path / "walkers.ckpt").as_posix()
    save = f"from walkers_module import Walkers; Walkers().save({path!r})"
    load = (
        "from modelly.core.model import Model; import walkers_module; "
        f"m = Model.load({path!r}); print([float(a.value) for a in m.agents])"
    )
    for code in (save, load):
        done = subprocess.run(
            [sys.executable, "-c", code],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[0.0, 1.0, 2.0, 3.0, 4.0]"
