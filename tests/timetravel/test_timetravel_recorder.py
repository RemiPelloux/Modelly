"""Tests for Recorder: the checkpoint ring, rewind and replay, scenarios, branches."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from timetravel_support import EXAMPLES, Drift, DriftScenario, fingerprint

from modelly import Model
from modelly.timetravel import Recorder

REPO = Path(__file__).resolve().parents[2]
STEPS = 60
REWIND = (0, 17, 30, 59)

# Records a run in a fresh interpreter, rewinds and replays, prints the state.
REPLAY = """
import sys
sys.path.insert(0, sys.argv[1])
from timetravel_support import EXAMPLES, fingerprint
from modelly.core import rng
from modelly.timetravel import Recorder
model = EXAMPLES["wolf_sheep"]()
with Recorder(model, every=7) as rec:
    model.run_for(40)
past = rec.at(23)
past.run_for(17)
print(rng.NATIVE, fingerprint(past) == fingerprint(model))
"""


def straight(name, steps=STEPS):
    """The fingerprint of an unrecorded run of ``steps`` steps."""
    model = EXAMPLES[name]()
    model.run_for(steps)
    return fingerprint(model)


@pytest.mark.parametrize("name", EXAMPLES)
def test_recording_and_rewinding_are_bit_identical(name):
    """A recorded run and every rewind-and-replay equal a straight run."""
    reference = straight(name)
    model = EXAMPLES[name]()
    with Recorder(model, every=10) as rec:
        model.run_for(STEPS)
    assert fingerprint(model) == reference
    for step in REWIND:
        past = rec.at(step)
        assert past.time == step
        past.run_for(STEPS - step)
        assert fingerprint(past) == reference


@pytest.mark.parametrize("name", EXAMPLES)
def test_rewind_equals_a_straight_run_to_that_step(name):
    """``at(step)`` is the state a straight run has at ``step``."""
    model = EXAMPLES[name]()
    with Recorder(model, every=10, compress=True) as rec:
        for _ in range(STEPS):
            model.step()
    assert fingerprint(rec.at(33)) == straight(name, 33)


@pytest.mark.parametrize("pure", [True, False])
def test_replay_with_either_core(pure):
    """Rewind and replay are bit-identical with the compiled and pure cores."""
    env = dict(os.environ)
    env.pop("MODELLY_PURE_PYTHON", None)
    if pure:
        env["MODELLY_PURE_PYTHON"] = "1"
    here = str(Path(__file__).parent)
    out = subprocess.run(
        [sys.executable, "-c", REPLAY, here],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    if not pure and out[0] == "False":
        pytest.skip("the compiled core is not built")
    assert out == [str(not pure), "True"]


def test_budget_evicts_the_oldest_but_keeps_the_first():
    """Beyond the budget the oldest go first; step 0 and the newest stay."""
    model = EXAMPLES["boltzmann"]()
    with Recorder(model, every=5) as unbounded:
        model.run_for(10)
    one = unbounded.nbytes // len(unbounded.steps)
    model = EXAMPLES["boltzmann"]()
    with Recorder(model, every=5, memory_budget=3 * one) as rec:
        model.run_for(40)
    assert rec.steps[0] == 0
    assert rec.steps[-1] == 40
    assert len(rec.steps) <= 3
    assert rec.nbytes <= 3 * one * 1.2
    assert fingerprint(rec.at(12)) == straight("boltzmann", 12)


def test_disk_ring_writes_loadable_checkpoints(tmp_path):
    """On disk each checkpoint is a whole file that Model.load reads."""
    model = EXAMPLES["schelling"]()
    with Recorder(model, every=10, directory=tmp_path / "ring") as rec:
        model.run_for(30)
    files = sorted(p.name for p in (tmp_path / "ring").iterdir())
    assert files == [f"step-{s!r}.ckpt" for s in sorted(rec.steps)]
    assert rec.nbytes == sum(p.stat().st_size for p in (tmp_path / "ring").iterdir())
    assert Model.load(tmp_path / "ring" / "step-20.0.ckpt").time == 20
    assert fingerprint(rec.at(25)) == straight("schelling", 25)


def test_disk_ring_deletes_evicted_files(tmp_path):
    """Evicted checkpoints leave no file behind."""
    model = EXAMPLES["boltzmann"]()
    with Recorder(model, every=1, memory_budget=1, directory=tmp_path) as rec:
        model.run_for(5)
    assert rec.steps == [0.0, 5.0]
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "step-0.0.ckpt",
        "step-5.0.ckpt",
    ]


def test_span_and_errors():
    """``at`` refuses steps outside the span; recording twice is refused."""
    model = EXAMPLES["boltzmann"]()
    rec = Recorder(model, every=4)
    with pytest.raises(ValueError, match="Nothing recorded"):
        rec.at(0)
    with rec:
        model.run_for(10)
        assert rec.recording
        with pytest.raises(RuntimeError, match="already"):
            Recorder(model).start()
    assert not rec.recording
    assert rec.span == (0.0, 10.0)
    assert rec.steps == [0.0, 4.0, 8.0]
    model.run_for(5)  # no longer recorded
    with pytest.raises(ValueError, match="outside"):
        rec.at(11)
    with pytest.raises(ValueError):
        Recorder(model, every=0)
    with pytest.raises(ValueError):
        Recorder(model, memory_budget=0)


def test_saving_while_recording(tmp_path):
    """``model.save`` and ``checkpoint_every`` work on a recorded model."""
    model = EXAMPLES["wolf_sheep"]()
    with Recorder(model, every=10):
        writer = model.checkpoint_every(15, str(tmp_path / "w-{time:03.0f}.ckpt"))
        model.run_for(30)
        writer.stop()
    resumed = Model.load(tmp_path / "w-015.ckpt")
    resumed.run_for(15)
    ours, theirs = fingerprint(resumed), fingerprint(model)
    del ours["events"], theirs["events"]  # the resumed run keeps its writer
    assert ours == theirs
    with Recorder(resumed, every=5) as rec:
        resumed.run_for(5)
    assert rec.steps == [30.0, 35.0]


def test_replay_with_a_changed_scenario():
    """A rewound model's scenario can change; the recording does not."""
    model = Drift(DriftScenario(rng=1))
    with Recorder(model, every=10) as rec:
        model.run_for(50)
    past = rec.at(30)
    level = past.level
    past.scenario.rate = 0.0
    past.run_for(20)
    assert past.level == level
    assert rec.at(30).scenario.rate == 1.0
    with pytest.raises(TypeError, match="frozen"):
        model.scenario.rate = 2.0


def test_branches_share_or_split_their_streams():
    """Branches continue one stream; reseeded branches get spawned seeds."""
    model = EXAMPLES["boltzmann"]()
    with Recorder(model, every=10) as rec:
        model.run_for(20)
    same = rec.branch(15, 3)
    for branch in same:
        branch.run_for(10)
    assert len({repr(fingerprint(b)) for b in same}) == 1
    split = rec.branch(15, 3, reseed=True)
    again = rec.branch(15, 3, reseed=True)
    for branch in split + again:
        branch.run_for(10)
    assert len({repr(fingerprint(b)) for b in split}) == 3
    assert [fingerprint(b) for b in split] == [fingerprint(b) for b in again]
    assert all(b.time == 25 for b in split)


def test_fractional_interval_and_event_driven_runs():
    """Checkpoints fall on multiples of ``every`` even between steps."""
    model = EXAMPLES["wolf_sheep"]()
    with Recorder(model, every=2.5) as rec:
        model.run_until(10)
    assert rec.steps == [0.0, 2.5, 5.0, 7.5, 10.0]
    assert fingerprint(rec.at(10)) == straight("wolf_sheep", 10)
