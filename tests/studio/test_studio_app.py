"""Every bundled example opens in Studio, rendered headless with Solara's test renderer."""

from pathlib import Path

import pytest

solara = pytest.importorskip("solara")
v = pytest.importorskip("ipyvuetify")

import modelly.examples  # noqa: E402
from modelly.studio import app  # noqa: E402
from modelly.studio.config import ENV_VAR, StudioConfig  # noqa: E402
from modelly.studio.session import StudioSession  # noqa: E402

ROOT = Path(modelly.examples.__file__).parent
EXAMPLES = modelly.examples.__all__
SCRUB_LABEL = "step (live: "


def file_target(name: str) -> str:
    """``modelly/examples/.../model.py:Class`` for a bundled example."""
    cls = getattr(modelly.examples, name)
    relative = cls.__module__.split(".")[2:]  # drop "modelly.examples"
    return f"{ROOT.joinpath(*relative).with_suffix('.py')}:{name}"


TOGGLE_TIMEOUT_S = 10  # generous: a busy Windows runner schedules threads late


def render(session: StudioSession):
    """Render the Studio app inside an AppLayout, as the server does."""

    @solara.component
    def Served():
        with solara.AppLayout():
            app.StudioApp(session)

    return solara.render(Served(), handle_error=False)[1]


def click(rc, label: str) -> None:
    """Click the button labelled ``label``."""
    rc.find(v.Btn, children=[label]).widget.click()


def scrubber(rc):
    """The timeline slider."""
    return next(
        w for w in rc.find(v.Slider).widgets if str(w.label).startswith(SCRUB_LABEL)
    )


@pytest.mark.parametrize("name", EXAMPLES)
def test_every_example_opens_runs_and_scrubs(name):
    """Build from the file target, render, step, run, scrub and show every tab."""
    config = StudioConfig(target=file_target(name))
    session = app.new_session(config)
    assert type(session.model).__name__ == name
    rc = render(session)
    click(rc, "Step")
    click(rc, "Run 10")
    assert session.model.time == pytest.approx(11) or not session.model.running
    live = session.model.time
    scrubber(rc).v_model = 2
    assert session.shown.time == 2
    click(rc, "Back to live")
    assert session.shown.time == live
    tabs = rc.find(v.Tabs).widget
    expected = {"Model": "space", "Agents": "agents", "Profiler": "profiler"}
    for index, (label, _) in enumerate(app.TABS):
        tabs.v_model = index
        titles = " ".join(str(t.children) for t in rc.find(v.CardTitle).widgets)
        assert expected.get(label, label.lower()) in titles.lower()


def test_replay_from_the_ui():
    """Scrub, change a value with restart off, replay from here."""
    session = app.new_session(StudioConfig(target=file_target("WolfSheep")))
    rc = render(session)
    rc.find(
        v.Checkbox, label="Restart the run when a value changes"
    ).widget.v_model = False
    click(rc, "Run 10")
    scrubber(rc).v_model = 4
    rc.find(v.TextField, label="initial_wolves").widget.v_model = "3"
    rc.find(v.TextField, label="initial_wolves").widget.fire_event("keyup.enter")
    assert session.model.time == 10  # restart is off: the run goes on
    click(rc, "Replay from here")
    assert session.model.time == 4
    assert session.model.scenario.initial_wolves == 3
    assert session.view is None


def test_a_changed_value_restarts_the_run():
    """With restart on (the default), changing a value starts a new run."""
    session = app.new_session(StudioConfig(target=file_target("BoltzmannWealth")))
    rc = render(session)
    click(rc, "Run 10")
    seed = rc.find(v.TextField, label="seed").widget
    seed.v_model = "9"
    seed.fire_event("keyup.enter")
    assert session.seed == 9
    assert session.model.time == 0
    agents = rc.find(v.TextField, label="n").widget
    agents.v_model = "12"
    agents.fire_event("keyup.enter")
    assert len(session.model.agents) == 12


def test_play_and_pause_toggle():
    """Play flips to Pause and back.

    The play loop steps on a thread, so each button may appear a moment after the click
    (later on slower runners): wait for it instead of asserting at once. Pause in the end
    in any case, so a failure cannot leave the loop running and the test session hanging.
    """
    session = app.new_session(StudioConfig(target=file_target("BoltzmannWealth")))
    rc = render(session)
    click(rc, "Play")
    try:
        pause = rc.find(v.Btn, children=["Pause"]).wait_for(timeout=TOGGLE_TIMEOUT_S)
        pause.widget.click()
        rc.find(v.Btn, children=["Play"]).wait_for(
            timeout=TOGGLE_TIMEOUT_S
        ).assert_single()
    finally:
        still_playing = rc.find(v.Btn, children=["Pause"])
        if len(still_playing):
            still_playing.widget.click()


def test_a_model_error_is_shown_not_raised(monkeypatch):
    """An exception in a step is logged and shown under the controls."""
    session = app.new_session(StudioConfig(target=file_target("BoltzmannWealth")))
    rc = render(session)

    def broken():
        raise RuntimeError("boom")

    monkeypatch.setattr(session.model, "step", broken)
    click(rc, "Step")
    rc.find(v.Alert, children=["RuntimeError: boom"]).assert_single()
    assert any("RuntimeError: boom" in line for line in session.log)


def test_lint_panel_explains_a_finding(tmp_path):
    """A finding is a button; clicking it shows the rule's explanation."""
    path = tmp_path / "rogue.py"
    path.write_text(
        "import random\n\nfrom modelly import Model\n\n\nclass Rogue(Model):\n"
        "    def step(self):\n        self.x = random.random()\n",
        encoding="utf-8",
    )
    session = app.new_session(StudioConfig(target=f"{path}:Rogue"))
    rc = render(session)
    rc.find(v.Tabs).widget.v_model = [label for label, _ in app.TABS].index("Lint")
    button = next(w for w in rc.find(v.Btn).widgets if "MDL001" in str(w.children))
    button.click()
    assert "Instead:" in str(rc.find(v.Html, tag="pre").widget.children)


def test_page_reads_the_config_from_the_environment(monkeypatch):
    """``Page`` is what the server shows; it needs the config in the environment."""
    config = StudioConfig(target=file_target("VirusOnNetwork"))
    monkeypatch.setenv(ENV_VAR, config.to_json())
    solara.render(app.Page(), handle_error=False)
    monkeypatch.delenv(ENV_VAR)
    with pytest.raises(RuntimeError, match=ENV_VAR):
        StudioConfig.from_environment()


def test_portrayal_from_an_app_module():
    """``--portrayal`` loads a function from a file, here an example's app.py."""
    target = file_target("BoltzmannWealth")
    portrayal = (
        str(ROOT / "basic" / "boltzmann_wealth_model" / "app.py") + ":agent_portrayal"
    )
    session = app.new_session(StudioConfig(target=target, portrayal=portrayal))
    assert session.portrayal.__name__ == "agent_portrayal"
