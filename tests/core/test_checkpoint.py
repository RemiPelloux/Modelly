"""Tests for model checkpoints: Model.save, Model.load and checkpoint_every."""

import json
import os
import pickle
import subprocess
import sys
from functools import partial
from pathlib import Path

import numpy as np
import pytest

import modelly
from modelly import Agent, CohortTable, Column, DataCollector, Model
from modelly.core import checkpoint, rng
from modelly.core.exceptions import CheckpointError
from modelly.examples import BoidFlockers, BoltzmannWealth, Schelling, WolfSheep
from modelly.examples.advanced.wolf_sheep.model import WolfSheepScenario
from modelly.examples.basic.boid_flockers.model import BoidsScenario
from modelly.examples.basic.boltzmann_wealth_model.model import BoltzmannScenario
from modelly.examples.basic.schelling.model import SchellingScenario
from modelly.time import Schedule

REPO = Path(__file__).resolve().parents[2]
HALF = 50
SEED = 42

EXAMPLES = {
    "wolf_sheep": lambda: WolfSheep(WolfSheepScenario(rng=SEED)),
    "boltzmann": lambda: BoltzmannWealth(BoltzmannScenario(rng=SEED)),
    "schelling": lambda: Schelling(SchellingScenario(rng=SEED)),
    "boids": lambda: BoidFlockers(BoidsScenario(rng=SEED)),
}

# Loads a checkpoint in a fresh interpreter, runs it on and saves the result.
RESUME = """
import sys
from modelly import Model
from modelly.core import rng
model = Model.load(sys.argv[1])
for _ in range(int(sys.argv[3])):
    model.step()
model.save(sys.argv[2])
print(rng.NATIVE)
"""


def _place(agent):
    """Where an agent is: its cell coordinate or its continuous position."""
    cell = getattr(agent, "cell", None)
    if cell is not None:
        return cell.coordinate
    position = getattr(agent, "position", None)
    return None if position is None else tuple(float(x) for x in position)


def _recorded(model):
    """The tables of the model's DataRecorder, if it has one."""
    recorder = getattr(model, "recorder", None)
    if recorder is None:
        return None
    return {k: v.to_dict() for k, v in recorder.get_all_dataframes().items()}


def fingerprint(model):
    """Everything a bit-identical resume must reproduce."""
    collector = getattr(model, "datacollector", None)
    return {
        "recorded": _recorded(model),
        "time": model.time,
        "random": model.random.getstate(),
        "rng": model.rng.bit_generator.state,
        "model_vars": collector and collector.model_vars,
        "agent_records": collector and collector._agent_records,
        "agents": [(a.unique_id, type(a).__name__, _place(a)) for a in model.agents],
    }


def run(model, steps):
    """Step ``model`` ``steps`` times and return it."""
    for _ in range(steps):
        model.step()
    return model


def resume_in_subprocess(saved, out, steps, *, pure=None):
    """Run RESUME in a fresh interpreter; return whether it used the C core."""
    env = dict(os.environ)
    if pure is True:
        env["MODELLY_PURE_PYTHON"] = "1"
    elif pure is False:
        env.pop("MODELLY_PURE_PYTHON", None)
    result = subprocess.run(
        [sys.executable, "-c", RESUME, str(saved), str(out), str(steps)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip() == "True"


@pytest.mark.parametrize("name", EXAMPLES)
def test_resume_in_a_fresh_process_is_bit_identical(name, tmp_path):
    """100 steps == 50 steps, save, load in a new process, 50 steps."""
    reference = fingerprint(run(EXAMPLES[name](), 2 * HALF))
    run(EXAMPLES[name](), HALF).save(tmp_path / "half.ckpt")
    resume_in_subprocess(tmp_path / "half.ckpt", tmp_path / "end.ckpt", HALF)
    assert fingerprint(Model.load(tmp_path / "end.ckpt")) == reference


@pytest.mark.parametrize("pure", [True, False])
def test_compiled_and_pure_random_load_each_others_checkpoints(pure, tmp_path):
    """A checkpoint saved with one FastRandom resumes identically in the other."""
    reference = fingerprint(run(EXAMPLES["wolf_sheep"](), 2 * HALF))
    run(EXAMPLES["wolf_sheep"](), HALF).save(tmp_path / "half.ckpt")
    native = resume_in_subprocess(
        tmp_path / "half.ckpt", tmp_path / "end.ckpt", HALF, pure=pure
    )
    if native == rng.NATIVE:
        pytest.skip("the compiled core is not built, so both sides are pure Python")
    assert fingerprint(Model.load(tmp_path / "end.ckpt")) == reference


def test_fast_random_pickles_across_implementations():
    """Both FastRandom classes pickle to one state that loads as this process's."""
    for source in (rng.PyFastRandom(3), rng.FastRandom(3)):
        source.random()
        clone = pickle.loads(pickle.dumps(source))  # noqa: S301
        assert type(clone) is rng.FastRandom
        assert [clone.randint(0, 99) for _ in range(50)] == [
            source.randint(0, 99) for _ in range(50)
        ]


class Saver(Agent):
    """An agent with columns and a recurring and a one-off event."""

    wealth = Column(int, default=1)

    def __init__(self, model):
        """Schedule a recurring payday and a one-off windfall."""
        super().__init__(model)
        self.paydays = model.schedule_recurring(self.payday, Schedule(interval=2))
        self.bonus = partial(self.windfall, 5)  # events hold callbacks weakly
        model.schedule_event(self.bonus, after=3)

    def payday(self):
        """Earn a random amount."""
        self.wealth += self.random.randint(0, 3)

    def windfall(self, amount):
        """Earn ``amount`` once."""
        self.wealth += amount


class Savings(Model):
    """A small model exercising columns, events, the collector and cohorts."""

    def __init__(self, rng=None):
        """Create savers, a collector and a cohort table."""
        super().__init__(rng=rng)
        Saver.create_agents(self, 10)
        self.cohorts = CohortTable(self.rng, age=np.int16)
        self.cohorts.add(100, age=0)
        self.datacollector = DataCollector(agent_reporters={"wealth": "wealth"})

    def step(self):
        """Thin the cohorts, add a saver, collect."""
        self.cohorts.thin(0.9)
        Saver(self)
        self.datacollector.collect(self)


def savings_state(model):
    """The parts of Savings a resume must reproduce."""
    table = model.columns[Saver]
    return (
        fingerprint(model),
        table.wealth.tolist(),
        [a.wealth for a in model.agents],
        model.cohorts["count"].tolist(),
    )


@pytest.mark.parametrize("compress", [False, True])
def test_columns_events_cohorts_resume(compress, tmp_path):
    """Columns, recurring and one-off events and cohorts resume identically."""
    reference = savings_state(run(Savings(rng=SEED), 10))
    run(Savings(rng=SEED), 2).save(tmp_path / "s.ckpt", compress=compress)
    restored = Savings.load(tmp_path / "s.ckpt")
    agent = next(iter(restored.agents))
    agent.wealth += 0  # per-agent column properties work after load
    assert agent.wealth == restored.columns[Saver].wealth[agent._column_row]
    assert savings_state(run(restored, 8)) == reference


def test_closure_event_is_refused_by_name(tmp_path):
    """An event whose callback is a nested function names the event."""
    model = Model(rng=1)

    def nested():
        pass

    model.keep = nested
    event = model.schedule_event(nested, at=4)
    with pytest.raises(CheckpointError, match=f"event {event.unique_id} at time 4"):
        model.save(tmp_path / "x.ckpt")


def test_lambda_reporter_is_refused_by_name(tmp_path):
    """A lambda anywhere in the model is refused with its qualified name."""
    model = Model(rng=1)
    model.datacollector = DataCollector({"n": lambda m: len(m.agents)})
    with pytest.raises(CheckpointError, match="<lambda>"):
        model.save(tmp_path / "x.ckpt")


def _rewrite_header(path, **changes):
    """Rewrite fields of a checkpoint's header in place."""
    magic, header, payload = path.read_bytes().split(b"\n", 2)
    header = json.loads(header) | changes
    path.write_bytes(b"\n".join([magic, json.dumps(header).encode(), payload]))


@pytest.mark.parametrize(
    ("field", "value"),
    [("format", 0), ("python", "2.7"), ("modelly", "0.1.0")],
)
def test_incompatible_version_is_refused(field, value, tmp_path):
    """Another format, Python or Modelly release is refused before unpickling."""
    path = tmp_path / "v.ckpt"
    Model(rng=1).save(path)
    _rewrite_header(path, **{field: value})
    with pytest.raises(CheckpointError, match=field):
        Model.load(path)


def test_patch_releases_are_compatible(tmp_path):
    """Only major.minor of Modelly must match."""
    path = tmp_path / "v.ckpt"
    Model(rng=1).save(path)
    _rewrite_header(path, modelly=f"{checkpoint._release(modelly.__version__)}.99")
    assert isinstance(Model.load(path), Model)


@pytest.mark.parametrize(
    "content", [b"not a checkpoint", checkpoint.MAGIC + b"{broken\n", b""]
)
def test_wrong_file_is_refused(content, tmp_path):
    """A file that is not a checkpoint, or has a broken header, is refused."""
    path = tmp_path / "w.ckpt"
    path.write_bytes(content)
    with pytest.raises(CheckpointError):
        Model.load(path)


def test_load_checks_the_class(tmp_path):
    """Load on a subclass refuses a checkpoint of another model class."""
    Model(rng=1).save(tmp_path / "m.ckpt")
    with pytest.raises(CheckpointError, match="not a Savings"):
        Savings.load(tmp_path / "m.ckpt")


def test_checkpoint_every_writes_resumable_files(tmp_path):
    """checkpoint_every saves on schedule; each file resumes identically."""
    reference = fingerprint(run(EXAMPLES["wolf_sheep"](), 10))
    model = EXAMPLES["wolf_sheep"]()
    writer = model.checkpoint_every(4, str(tmp_path / "ws-{time:03.0f}.ckpt"))
    run(model, 10)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["ws-004.ckpt", "ws-008.ckpt"]
    assert fingerprint(model) == reference
    restored = run(Model.load(tmp_path / "ws-004.ckpt"), 6)
    assert fingerprint(restored) == reference
    writer.stop()
    run(model, 4)
    assert len(list(tmp_path.iterdir())) == 2
    with pytest.raises(ValueError, match="interval"):
        model.checkpoint_every(0, "never")
