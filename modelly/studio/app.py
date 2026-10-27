"""The Studio page: the layout of the panels, and ``Page``, which the server shows.

``StudioApp(session)`` is the whole app for one session, which the tests render headless.
``Page`` is what ``modelly studio`` serves: it reads the ``StudioConfig`` from the
environment, loads the model class once per server, and gives each browser tab a session.
"""

from __future__ import annotations

import functools
import warnings

import solara

from modelly.plugins import load_all
from modelly.studio.config import StudioConfig
from modelly.studio.loader import load_model_class, load_portrayal
from modelly.studio.panels import ExportPanel, ParameterPanel, RunControls
from modelly.studio.session import StudioSession
from modelly.studio.state import use_studio_state
from modelly.studio.tools import LintPanel, LogPanel, ProfilerPanel
from modelly.studio.views import AgentTable, Scrubber, SeriesView, SpaceView

TITLE = "Modelly Studio"


@solara.component
def StudioApp(session: StudioSession):
    """The Studio layout for one session: sidebar controls, views and tool tabs."""
    state = use_studio_state(session)
    solara.use_effect(state.drawn.set, [state.revision.value])
    solara.Title(f"{TITLE}: {session.model_class.__name__}")
    with solara.AppBar():
        solara.AppBarTitle(f"{TITLE} · {session.model_class.__name__}")
    with solara.Sidebar(), solara.Column():
        RunControls(state)
        ParameterPanel(state)
        ExportPanel(state)
    tab = solara.use_reactive(0)
    with solara.Column():
        Scrubber(state)
        tabs = all_tabs()
        with solara.v.Tabs(v_model=tab.value, on_v_model=tab.set):
            for name, _ in tabs:
                solara.v.Tab(children=[name])
        tabs[tab.value][1](state)


def ModelTab(state):
    """The space view and the reporters plot, side by side."""
    with solara.Columns([1, 1]):
        SpaceView(state)
        SeriesView(state)


TABS = (
    ("Model", ModelTab),
    ("Agents", AgentTable),
    ("Profiler", ProfilerPanel),
    ("Lint", LintPanel),
    ("Log", LogPanel),
)
# A plugin's entry point names a component taking the StudioState, like the TABS views.
VIEWS_GROUP = "modelly.studio_views"


@functools.cache
def all_tabs() -> tuple:
    """The built-in tabs, then one per ``modelly.studio_views`` plugin, named after it.

    A view that fails to load is left out with a ``RuntimeWarning``.
    """
    loaded, errors = load_all(VIEWS_GROUP)
    for error in errors.values():
        warnings.warn(f"{error}; Studio shows the other views", RuntimeWarning, 2)
    return TABS + tuple(loaded.items())


@functools.cache
def _loaded(config_json: str):
    """The config, model class and portrayal, loaded once per server."""
    config = StudioConfig.from_json(config_json)
    portrayal = load_portrayal(config.portrayal) if config.portrayal else None
    return config, load_model_class(config.target), portrayal


def new_session(config: StudioConfig) -> StudioSession:
    """A session for one browser tab."""
    config, model_class, portrayal = _loaded(config.to_json())
    return StudioSession(model_class, config, portrayal)


@solara.component
def Page():
    """The page ``modelly studio`` serves: one session per browser tab."""
    config = StudioConfig.from_environment()
    session = solara.use_memo(lambda: new_session(config), [])
    StudioApp(session)
