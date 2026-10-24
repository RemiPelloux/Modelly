"""Tests for the Studio session: build, step, profile, scrub, replay, lint and export."""

import io

import pandas as pd
import pytest

pytest.importorskip("solara")

from modelly.core.model import Model
from modelly.examples import (
    BoltzmannWealth,
    WolfSheep,
)
from modelly.examples.advanced.wolf_sheep.model import WolfSheepScenario
from modelly.studio import data
from modelly.studio.config import StudioConfig
from modelly.studio.session import StudioSession
from modelly.studio.timeline import GuardedRecorder, ReplayTimeline
from modelly.timetravel.snapshot import model_state

WOLF_SHEEP = "modelly.examples.advanced.wolf_sheep.model:WolfSheep"
SEED = 7


def session_for(cls, target: str, **options) -> StudioSession:
    """A session for ``cls`` with seed ``SEED``."""
    return StudioSession(cls, StudioConfig(target=target, seed=SEED, **options))


def straight(steps: int) -> WolfSheep:
    """A Wolf-Sheep run of ``steps`` steps with seed ``SEED``, unrecorded."""
    model = WolfSheep(WolfSheepScenario(rng=SEED))
    if steps:
        model.run_for(steps)
    return model


def test_the_first_run_uses_the_defaults_and_the_seed():
    """The panel starts on the Scenario defaults; the model is built with them."""
    session = session_for(WolfSheep, WOLF_SHEEP)
    assert session.values["initial_sheep"] == WolfSheepScenario.initial_sheep
    assert model_state(session.model) == model_state(straight(0))
    assert isinstance(session.timeline, GuardedRecorder)


def test_step_profiles_each_step_and_keeps_the_last_ones():
    """Every step is profiled; only the last ``profile_steps`` are summed."""
    session = session_for(WolfSheep, WOLF_SHEEP, profile_steps=3)
    assert session.step(5) == 5
    assert session.model.time == 5
    assert len(session.records) == 3
    report = session.profile_report()
    assert "Sheep.step (shuffle_do)" in report
    assert "us/agent" in report


def test_scrubbing_shows_the_straight_run_state():
    """Scrubbing back restores the state a straight run reaches at that step."""
    session = session_for(WolfSheep, WOLF_SHEEP)
    session.step(12)
    session.scrub(5)
    assert session.shown.time == 5
    assert model_state(session.shown) == model_state(straight(5))
    assert session.model.time == 12  # the live run is untouched
    session.scrub(12)
    assert session.view is None


def test_stepping_returns_to_the_live_model():
    """A step after scrubbing advances the live model and shows it again."""
    session = session_for(WolfSheep, WOLF_SHEEP)
    session.step(4)
    session.scrub(1)
    session.step()
    assert session.view is None
    assert session.model.time == 5


def test_replay_with_a_changed_value_branches_the_run():
    """Replay from a scrubbed step continues with the new scenario value."""
    session = session_for(WolfSheep, WOLF_SHEEP)
    session.step(10)
    session.scrub(4)
    session.values["wolf_reproduce"] = 0.5
    session.replay()
    assert session.model.time == 4
    assert session.model.scenario.wolf_reproduce == 0.5
    session.step(3)
    session.scrub(5)  # the new run's timeline starts at the replay step
    assert session.timeline.span == (4.0, 7.0)
    assert any("replayed from step 4" in line for line in session.log)


def test_replay_without_changes_continues_the_same_run():
    """Replaying with nothing changed gives the straight run's states."""
    session = session_for(WolfSheep, WOLF_SHEEP)
    session.step(8)
    session.scrub(3)
    session.replay()
    session.step(5)
    assert model_state(session.model) == model_state(straight(8))


def test_replay_with_a_new_seed_reseeds():
    """A changed seed reseeds the replayed model."""
    session = session_for(WolfSheep, WOLF_SHEEP)
    session.step(6)
    session.scrub(2)
    session.seed = SEED + 1
    session.replay()
    session.step(4)
    assert model_state(session.model) != model_state(straight(6))


class Unpicklable(Model):
    """Holds a lambda, so no checkpoint of it can be written."""

    def __init__(self, rng=None):
        """A counter driven by the model's generator, and a lambda pickle cannot save."""
        super().__init__(rng=rng)
        self.draw = lambda: self.random.random()  # noqa: PLW0108 - the lambda is the point
        self.total = 0.0

    def step(self):
        """Add one draw."""
        self.total += self.draw()


UNPICKLABLE = "tests.studio.test_studio_session:Unpicklable"


def test_a_model_that_cannot_be_checkpointed_replays():
    """A model holding a lambda: the scrubber replays the run from its start instead."""
    session = session_for(Unpicklable, UNPICKLABLE)
    assert isinstance(session.timeline, ReplayTimeline)
    assert session.replaying
    session.step(6)
    session.scrub(3)
    again = Unpicklable(rng=SEED)
    again.run_for(3)
    assert session.shown.total == again.total
    assert any("no checkpoints" in line for line in session.log)


def test_replay_timeline_rejects_steps_outside_the_run():
    """A replay timeline accepts the steps of the run so far only."""
    model = BoltzmannWealth()
    timeline = ReplayTimeline(BoltzmannWealth, model)
    with pytest.raises(ValueError, match="outside"):
        timeline.at(3)
    assert timeline.steps == [0.0]


def test_reset_applies_the_panel_values():
    """Reset rebuilds the model from the panel and starts a new timeline at 0."""
    target = "modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"
    session = session_for(BoltzmannWealth, target)
    session.step(3)
    session.values["n"] = 17
    session.reset()
    assert session.model.time == 0
    assert len(session.model.agents) == 17
    assert session.timeline.span == (0.0, 0.0)


def test_step_stops_when_the_model_stops():
    """``step`` takes fewer steps when the model sets running to False."""
    target = "modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"
    session = session_for(BoltzmannWealth, target)
    session.model.running = False
    assert session.step(3) == 0
    assert "stopped" in session.log[-1]


class Rogue(Model):
    """A model that draws from the global random module (MDL001)."""

    def step(self):
        """Nothing."""


ROGUE_SOURCE = """\
import random

from modelly import Model


class Rogue(Model):
    def step(self):
        self.x = random.random()
"""


def test_lint_checks_the_target_file(tmp_path):
    """The lint panel lints the file the target names."""
    path = tmp_path / "rogue.py"
    path.write_text(ROGUE_SOURCE, encoding="utf-8")
    session = StudioSession(Rogue, StudioConfig(target=f"{path}:Rogue"))
    assert session.source_file() == path
    assert [f.rule.code for f in session.lint()] == ["MDL001"]


def test_lint_of_a_dotted_target_uses_the_class_source():
    """Without a file in the target, lint reads the module the class comes from."""
    session = session_for(WolfSheep, WOLF_SHEEP)
    assert session.source_file().name == "model.py"
    assert session.lint() == []


def test_exports(tmp_path):
    """Figures, data, checkpoint and animation of the shown state."""
    session = session_for(WolfSheep, WOLF_SHEEP)
    session.step(3)
    assert data.space_image(session, "png").startswith(b"\x89PNG")
    assert b"<svg" in data.space_image(session, "svg")
    assert data.series_image(session.shown, "png").startswith(b"\x89PNG")
    frame = pd.read_csv(io.BytesIO(data.data_bytes(session.shown)))
    assert list(frame.columns)[1:] == ["Wolves", "Sheep", "Grass"]
    assert len(frame) == 4
    checkpoint = tmp_path / "state.ckpt"
    checkpoint.write_bytes(data.checkpoint_file(session.shown))
    assert model_state(WolfSheep.load(checkpoint)) == model_state(session.shown)
    assert data.animation_bytes(session).startswith(b"GIF8")
    with pytest.raises(ValueError, match="figure format"):
        data.figure_bytes(data.series_figure(session.shown), "bmp")


def test_parquet_export():
    """Parquet export when pyarrow is installed."""
    pytest.importorskip("pyarrow")
    session = session_for(WolfSheep, WOLF_SHEEP)
    payload = data.data_bytes(session.shown, "parquet")
    assert pd.read_parquet(io.BytesIO(payload)).shape[0] == 1
    assert data.parquet_available()


def test_agent_table_filters_by_class():
    """The table lists agents by unique_id, filtered by class."""
    session = session_for(WolfSheep, WOLF_SHEEP)
    classes = data.agent_classes(session.model)
    assert classes[0] == data.ALL_CLASSES
    assert {"Wolf", "Sheep", "GrassPatch"} <= set(classes)
    wolves = data.agent_table(session.model, "Wolf", rows=5)
    assert len(wolves) == 5
    assert set(wolves["class"]) == {"Wolf"}
    assert list(wolves["unique_id"]) == sorted(wolves["unique_id"])


def test_models_without_space_or_reporters():
    """Missing views give None rather than raising."""
    session = session_for(BoltzmannWealth, "x:BoltzmannWealth")
    session.model.datacollector = None
    assert data.model_series(session.model) is None
    assert data.series_figure(session.model) is None
    assert data.data_bytes(session.model) is None
    session.model.grid = None
    assert data.space_image(session) is None
    assert data.animation_bytes(session) is None


def test_timeline_steps_are_sampled():
    """An animation of a long run is sampled to MAX_FRAMES frames at most."""
    assert data.timeline_steps((0.0, 3.0)) == [0.0, 1.0, 2.0, 3.0]
    long = data.timeline_steps((0.0, data.MAX_FRAMES * 3.0))
    assert len(long) <= data.MAX_FRAMES + 1
