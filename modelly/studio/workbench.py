"""The workbench's browser side: keyboard shortcuts, the panel's width, what the browser keeps.

``Workbench`` is the handle between the side panel and the views. Drag it, or focus it and
press the left and right arrows, to resize the panel. The same Vue template
(``workbench.vue``) listens to the page's keys: space plays or pauses, the left and right
arrows step back and forward through the run (forward from the live step takes a new step),
End returns to the live step, and ``?`` lists the shortcuts. It keeps the open panel, the
open tab and the panel's width in the browser's local storage, and restores them when
Studio opens again.
"""

from __future__ import annotations

import ipyvuetify
import solara
import traitlets

from modelly.studio.i18n import t
from modelly.studio.state import StudioState

# (key as the help shows it, what it does), in the order the help lists them.
SHORTCUTS = (
    ("Space", "Play or pause"),
    ("→", "Step forward, or forward through the timeline"),
    ("←", "Back through the timeline"),
    ("End", "Back to live"),
    ("?", "Show or hide the shortcuts"),
)
LABELS = ("Keyboard shortcuts", "Resize the side panel", "Close")


class WorkbenchWidget(ipyvuetify.VuetifyTemplate):
    """The resize handle, the key listener and the shortcuts' help, in one template."""

    template_file = (__file__, "workbench.vue")

    panel = traitlets.Unicode(None, allow_none=True).tag(sync=True)
    tab = traitlets.Unicode("").tag(sync=True)
    shortcuts = traitlets.List([]).tag(sync=True)
    labels = traitlets.Dict({}).tag(sync=True)
    help = traitlets.Bool(False).tag(sync=True)
    handler = traitlets.Any(None)

    def vue_key(self, name: str) -> None:
        """A shortcut pressed in the browser: ``play``, ``forward``, ``back`` or ``live``."""
        if self.handler is not None:
            self.handler(name)


def press(state: StudioState, name: str) -> None:
    """What a shortcut does: the same as the button it stands for, when that is enabled."""
    session, playing = state.session, state.playing.value
    idle = not playing and session.model.running
    if name == "play" and (playing or idle):
        state.playing.set(not playing)
    elif playing:
        return
    elif name == "forward":
        _forward(state, idle)
    elif name == "back" and session.shown.time > session.timeline.span[0]:
        state.act(session.scrub, session.shown.time - 1)
    elif name == "live" and session.view is not None:
        state.act(session.scrub, session.timeline.span[1])


def _forward(state: StudioState, idle: bool) -> None:
    """One step forward: through the timeline when it shows the past, else a new step."""
    session = state.session
    if session.view is not None:
        state.act(session.scrub, session.shown.time + 1)
    elif idle:
        state.act(session.step, 1)


@solara.component
def Workbench(
    state: StudioState, panel: solara.Reactive[str | None], tab: solara.Reactive[str]
):
    """The panel's resize handle; restores and keeps the open panel and tab."""
    WorkbenchWidget.element(
        panel=panel.value,
        on_panel=panel.set,
        tab=tab.value,
        on_tab=tab.set,
        shortcuts=[[key, t(what)] for key, what in SHORTCUTS],
        labels={label: t(label) for label in LABELS},
        handler=lambda name: press(state, name),
    )


__all__ = ["SHORTCUTS", "Workbench", "WorkbenchWidget", "press"]
