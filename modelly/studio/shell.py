"""Studio's frame, laid out like a notebook workbench.

The top bar holds the model's name and the run toolbar; an activity bar on the left opens the
Parameters or the Export panel (a second click closes it); the views are document tabs; the
timeline sits under them and a status bar at the foot says what is shown. ``Layout`` replaces
Solara's app bar and drawer, which Studio does not use. The look is in
``modelly/templates/studio.css``.
"""

from __future__ import annotations

from pathlib import Path

import solara

from modelly.studio.i18n import t
from modelly.studio.panels import ExportPanel, ParameterPanel, PlaybackPanel, RunToolbar
from modelly.studio.state import StudioState

# (panel name, icon) for each button of the activity bar: icons of the Material Design
# Icons font Solara ships (an older set: check a name exists in its fonts.css).
PANELS = (("Parameters", "mdi-tune"), ("Export", "mdi-download"))
MARK = """<svg viewBox="0 0 32 32" width="22" height="22" aria-hidden="true">
<rect width="32" height="32" rx="8" fill="#1d2b46"/>
<g fill="#6c8cff"><rect x="5" y="5" width="6" height="6" rx="1.6"/>
<rect x="13" y="5" width="6" height="6" rx="1.6"/><rect x="5" y="13" width="6" height="6" rx="1.6"/>
<rect x="5" y="21" width="6" height="6" rx="1.6"/><rect x="13" y="21" width="6" height="6" rx="1.6"/>
<rect x="21" y="21" width="6" height="6" rx="1.6"/></g>
<g fill="#2fd4a7"><rect x="21" y="5" width="6" height="6" rx="1.6"/>
<rect x="21" y="13" width="6" height="6" rx="1.6"/></g>
<rect x="13" y="13" width="6" height="6" rx="1.6" fill="#ff4f8b"/></svg>"""


@solara.component
def Layout(children=[]):  # noqa: B006 (Solara's layout signature)
    """The page around Studio: none of Solara's app bar or drawer."""
    solara.Column(children=children, gap="0", classes=["mx-page"])


def target_name(target: str) -> str:
    """The file or module a target names, without its folders: ``model.py:WolfSheep``."""
    where, _, name = target.rpartition(":")
    return f"{Path(where).name or where}:{name}" if where else target


@solara.component
def TopBar(state: StudioState):
    """The mark, the model's class and target, and the run toolbar."""
    session = state.session
    with solara.Row(classes=["mx-topbar"], gap="0"):
        solara.HTML(tag="span", unsafe_innerHTML=MARK, classes=["mx-mark"])
        with solara.Column(classes=["mx-title"], gap="0"):
            solara.Text(session.model_class.__name__, classes=["mx-model"])
            solara.Text(
                f"Modelly Studio, {target_name(session.config.target)}",
                classes=["mx-target"],
            )
        RunToolbar(state)


def _activity_button(name: str, icon: str, open_panel) -> None:
    """The activity bar's button for one panel: opens it, or closes it when open."""
    active = open_panel.value == name
    solara.Button(
        icon_name=icon,
        icon=True,
        on_click=lambda: open_panel.set(None if active else name),
        classes=["mx-activity-button", "is-active" if active else ""],
        attributes={"aria-label": t(name), "title": t(name), "aria-pressed": str(active).lower()},
    )  # fmt: skip


@solara.component
def SidePanel(state: StudioState):
    """The activity bar and the open panel; a closed panel keeps its state, hidden."""
    open_panel = solara.use_reactive(PANELS[0][0])
    with solara.Row(classes=["mx-side"], gap="0"):
        with solara.Column(classes=["mx-activity"], gap="0"):
            for name, icon in PANELS:
                _activity_button(name, icon, open_panel)
        hidden = "" if open_panel.value == "Parameters" else "mx-hidden"
        with solara.Column(classes=["mx-panel", hidden], gap="0"):
            ParameterPanel(state)
            PlaybackPanel(state)
        hidden = "" if open_panel.value == "Export" else "mx-hidden"
        with solara.Column(classes=["mx-panel", hidden], gap="0"):
            ExportPanel(state)


def _shown_label(state: StudioState) -> tuple[str, str]:
    """What the views show (the live run or a past step) and its status class."""
    session = state.session
    if session.view is None:
        return t("Live run"), "is-live"
    return t("Past step {step}").format(step=f"{session.shown.time:g}"), "is-past"


def _activity(state: StudioState) -> str:
    """Whether the run is playing, stopped by the model, or waiting."""
    if state.playing.value:
        return t("Playing")
    return t("Idle") if state.session.model.running else t("Stopped")


@solara.component
def StatusBar(state: StudioState):
    """The state of the run: live or past, seed, agents, playing or not."""
    state.revision.get()
    session = state.session
    shown, kind = _shown_label(state)
    with solara.Row(classes=["mx-status"], gap="0"):
        solara.Text(shown, classes=["mx-status-item", kind])
        solara.Text(f"seed {session.seed}", classes=["mx-status-item"])
        count = len(session.shown.agents)
        solara.Text(f"{count:,} agents", classes=["mx-status-item"])
        solara.Text(_activity(state), classes=["mx-status-item"])
        solara.HTML(
            tag="a",
            unsafe_innerHTML="Made with Solara",
            attributes={"href": "https://solara.dev", "target": "_blank", "rel": "noopener"},
            classes=["mx-status-item", "mx-credit"],
        )  # fmt: skip
