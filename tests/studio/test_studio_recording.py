"""The session script: replaying what a Studio session did gives the live run's state."""

import enum
import subprocess
import sys
from pathlib import Path

import pytest

from modelly.studio.config import StudioConfig
from modelly.studio.recording import NEW_RUN, REPLAY, SessionRecording, literal
from modelly.studio.session import StudioSession
from modelly.timetravel.snapshot import agent_state

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = "modelly.examples"
WOLF_SHEEP = f"{EXAMPLES}.advanced.wolf_sheep.model:WolfSheep"
# Checkpointable (WolfSheep, Boltzmann), replayed by rerunning (Epstein, Sugarscape),
# a network (virus) and a model without a Scenario class (Conway).
TARGETS = [
    WOLF_SHEEP,
    f"{EXAMPLES}.basic.boltzmann_wealth_model.model:BoltzmannWealth",
    f"{EXAMPLES}.advanced.epstein_civil_violence.model:EpsteinCivilViolence",
    f"{EXAMPLES}.advanced.sugarscape_g1mt.model:SugarscapeG1mt",
    f"{EXAMPLES}.basic.virus_on_network.model:VirusOnNetwork",
    f"{EXAMPLES}.basic.conways_game_of_life.model:ConwaysGameOfLife",
]
RUN_TIMEOUT_S = 120


def session_of(target: str) -> StudioSession:
    """A Studio session on ``target``, built without the Solara app."""
    from modelly.studio.loader import load_model_class  # noqa: PLC0415

    return StudioSession(load_model_class(target), StudioConfig(target=target))


def state_of(model) -> tuple:
    """Everything that makes two model states the same: time, agents, generators, data."""
    agents = sorted(
        (a.unique_id, type(a).__name__, repr(sorted(agent_state(a).items())))
        for a in model.agents
    )
    collector = getattr(model, "datacollector", None)
    data = None if collector is None else collector.get_model_vars_dataframe().to_dict()
    random = (model.rng.bit_generator.state, model.random.getstate())
    return model.time, agents, random, data, dict(model.scenario)


def replayed(script: str):
    """The model ``replay()`` in ``script`` returns, run in this process."""
    namespace = {"__name__": "session_script"}
    exec(compile(script, "session.py", "exec"), namespace)  # noqa: S102 (our own script)
    return namespace["replay"]()


def one_number(session: StudioSession) -> str | None:
    """A numeric parameter of the session's panel to change, or None."""
    numbers = [
        p.name for p in session.parameters if p.kind in ("int", "fraction", "float")
    ]
    return numbers[0] if numbers else None


def change(session: StudioSession, name: str) -> None:
    """Nudge parameter ``name`` up."""
    value = session.values[name]
    session.values[name] = value + 1 if isinstance(value, int) else value * 1.1


@pytest.mark.parametrize("target", TARGETS)
def test_the_script_rebuilds_the_live_run(target):
    """New run, steps, scrub back, replay with a changed seed, more steps: same state."""
    session = session_of(target)
    name = one_number(session)
    if name is not None:
        change(session, name)
    session.seed = 5
    session.reset()
    session.step(8)
    session.scrub(3)
    session.seed = 11
    session.replay()
    session.step(4)
    assert session.model.time == 7
    model = replayed(session.recording.script(session.model.time))
    assert state_of(model) == state_of(session.model)


def test_a_replay_with_changed_scenario_values():
    """A changed Scenario value applied at the replayed step is in the script."""
    session = session_of(WOLF_SHEEP)
    session.step(6)
    session.scrub(2)
    session.values["sheep_reproduce"] = 0.09
    session.replay()
    session.step(3)
    script = session.recording.script(session.model.time, "WolfSheep")
    assert "model.scenario.sheep_reproduce = 0.09" in script
    assert (
        "reseed_model" not in script.split("def replay")[1]
    )  # the seed did not change
    assert state_of(replayed(script)) == state_of(session.model)


def test_scrubbing_alone_is_not_recorded():
    """Scrubbing and coming back to live leaves the record as one straight run."""
    session = session_of(WOLF_SHEEP)
    session.step(5)
    session.scrub(2)
    session.scrub(5)
    assert session.recording.straight
    assert state_of(replayed(session.recording.script(5))) == state_of(session.model)


def test_reset_starts_a_new_record():
    """Reset forgets the earlier run and its replays."""
    session = session_of(WOLF_SHEEP)
    session.step(4)
    session.scrub(1)
    session.replay()
    assert not session.recording.straight
    session.reset()
    assert [s.kind for s in session.recording.segments] == [NEW_RUN]


def test_the_script_runs_as_a_file(tmp_path):
    """``python session.py`` runs from any folder and reports the final step."""
    session = session_of(WOLF_SHEEP)
    session.step(3)
    path = tmp_path / "session.py"
    path.write_text(session.recording.script(3, "WolfSheep"), encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(path)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={"PYTHONPATH": str(ROOT), "PATH": ""},
        timeout=RUN_TIMEOUT_S,
        check=True,
    )
    assert done.stdout.strip() == "WolfSheep at step 3"


class Colour(enum.Enum):
    """An enum a parameter could take."""

    RED = 1


def test_literal_writes_enums_by_name():
    """Plain values are their repr; an Enum member is looked up by module and name."""
    assert literal(0.1) == "0.1"
    assert literal("a") == "'a'"
    text = literal(Colour.RED)
    assert eval(text, {"importlib": __import__("importlib")}) is Colour.RED  # noqa: S307


def test_segments_and_errors():
    """A replay cuts the run before it; an empty record has no script."""
    recording = SessionRecording("model.py:Model")
    with pytest.raises(ValueError, match="nothing recorded"):
        recording.script(0)
    recording.new_run({"n": 3}, 7)
    recording.replayed(4, {"n": 5}, None)
    assert [s.kind for s in recording.segments] == [NEW_RUN, REPLAY]
    assert recording.segments[0].steps == 4
    body = recording.body(6)
    assert body.count("    model.step()") == 2
    assert "for _ in range(2):" in body
