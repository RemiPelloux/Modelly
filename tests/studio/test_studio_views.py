"""The new tabs rendered headless: map, ensemble, assimilation, experiments, analysis."""

import pandas as pd
import pytest

solara = pytest.importorskip("solara")
v = pytest.importorskip("ipyvuetify")

from modelly.sensitivity.results import SensitivityResult  # noqa: E402
from modelly.studio import app  # noqa: E402
from modelly.studio.config import StudioConfig  # noqa: E402
from modelly.studio.mapview import MapWidget  # noqa: E402
from modelly.studio.session import StudioSession  # noqa: E402
from tests.studio.models import Growth  # noqa: E402
from tests.studio.test_studio_app import click, render  # noqa: E402
from tests.studio.test_studio_browser import sweep  # noqa: E402
from tests.studio.test_studio_ensembles import truth_observations  # noqa: E402
from tests.studio.test_studio_recording import WOLF_SHEEP  # noqa: E402
from tests.studio.test_studio_scene import Crowd  # noqa: E402

TAB_NAMES = [name for name, _ in app.TABS]


def open_tab(rc, name: str) -> None:
    """Switch the main tabs to ``name``."""
    rc.find(v.Tabs).widget.v_model = TAB_NAMES.index(name)


def buttons(rc) -> list[str]:
    """The labels of every button on the page."""
    widgets = rc.find(v.Btn).widgets
    return [" ".join(c for c in b.children if isinstance(c, str)) for b in widgets]


def texts(rc) -> str:
    """Everything the page's HTML widgets say, joined."""
    from ipywidgets import HTML  # noqa: PLC0415

    found = [str(w.value) for w in rc.find(HTML).widgets]
    found += [str(w.children) for w in rc.find(v.Html).widgets]
    return " ".join(found)


def test_the_map_tab_sends_the_scene():
    """The WebGL widget holds the shown model's scene; the checkbox forces Canvas 2D."""
    session = app.new_session(StudioConfig(target=WOLF_SHEEP))
    rc = render(session)
    open_tab(rc, "Map")
    widget = rc.find(MapWidget).widget
    assert widget.scene["counts"][0] == len(session.model.agents)
    assert widget.force_canvas is False
    click(rc, "Step")
    assert rc.find(MapWidget).widget.scene["counts"][0] == len(session.model.agents)
    checkbox = next(
        w for w in rc.find(v.Checkbox).widgets if "Canvas 2D" in str(w.label)
    )
    checkbox.v_model = True
    assert rc.find(MapWidget).widget.force_canvas is True


def test_large_models_leave_the_space_to_the_map():
    """Above the Matplotlib limit the Model tab says so instead of drawing."""
    session = StudioSession(
        Crowd, StudioConfig(target="tests.studio.test_studio_scene:Crowd")
    )
    session.values["n"] = 20_000
    session.reset()
    rc = render(session)
    assert "too many to redraw" in texts(rc)


def test_the_ensemble_tab_runs_replicates():
    """Run ensemble draws the bands and offers them as CSV."""
    session = app.new_session(StudioConfig(target=WOLF_SHEEP))
    rc = render(session)
    open_tab(rc, "Ensemble")
    rc.find(v.TextField, label="replicates").widget.v_model = "3"
    rc.find(v.TextField, label="ensemble steps").widget.v_model = "4"
    click(rc, "Run ensemble")
    assert "Bands (CSV)" in buttons(rc)


def test_the_assimilation_tab(tmp_path):
    """With an observations file: run the particle filter, then the Kalman filter."""
    path = tmp_path / "observed.csv"
    rows = [f"{o.time},{o.values['count']}" for o in truth_observations()]
    path.write_text("time,count\n" + "\n".join(rows) + "\n", encoding="utf-8")
    config = StudioConfig(target="tests.studio.models:Growth", observations=str(path))
    session = StudioSession(Growth, config)
    rc = render(session)
    open_tab(rc, "Assimilation")
    assert "10 observation(s)" in texts(rc)
    click(rc, "Assimilate")
    assert "History (CSV)" in buttons(rc)
    rc.find(v.Select, label="method").widget.v_model = "ensemble Kalman filter"
    rc.find(v.Select, label="parameters to adjust").widget.v_model = ["rate"]
    click(rc, "Assimilate")
    assert "History (CSV)" in buttons(rc)
    assert not [e for e in session.log if e.startswith("error")]


def test_the_tabs_without_inputs_say_how_to_get_them():
    """No --observations, --results or --analysis: each tab explains its option."""
    session = app.new_session(StudioConfig(target=WOLF_SHEEP))
    rc = render(session)
    for name, option in (
        ("Assimilation", "--observations"),
        ("Experiments", "--results"),
        ("Analysis", "--analysis"),
    ):
        open_tab(rc, name)
        assert option in texts(rc)


def test_the_experiments_and_analysis_tabs(tmp_path):
    """A results store is browsed; a session's analyses are drawn."""
    pytest.importorskip("duckdb")
    config = StudioConfig(target=WOLF_SHEEP, results=str(sweep(tmp_path)))
    session = app.new_session(config)
    table = pd.DataFrame({"mu_star": [1.0, 2.0]}, index=["a", "b"])
    session.analyses.append(("screen", SensitivityResult("custom", table, "mu_star")))
    rc = render(session)
    open_tab(rc, "Experiments")
    assert "12 run(s)" in texts(rc)
    assert "Selected runs (CSV)" in buttons(rc)
    open_tab(rc, "Analysis")
    assert "screen: custom, ranked by mu_star" in texts(rc)


def test_the_export_panel_offers_the_session_and_the_bundle():
    """The sidebar exports the live run's script and its bundle."""
    rc = render(app.new_session(StudioConfig(target=WOLF_SHEEP)))
    labels = buttons(rc)
    assert "Session script (live run, .py)" in labels
    assert "Bundle (live run, zip)" in labels
