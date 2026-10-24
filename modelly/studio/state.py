"""The reactive state Studio's components share, and running session calls safely.

``StudioState`` bundles the session with three reactive values: ``revision``, bumped after
every change so the views redraw; ``playing``; and ``error``, the last failure shown under
the controls. ``drawn`` is set each time the page has drawn a revision, which paces the
play loop. ``act`` runs a session call, logs any exception the model raised, and bumps
the revision either way.
"""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import solara

from modelly.studio.session import StudioSession

DEFAULT_INTERVAL_MS = 100


@dataclass
class StudioState:
    """The session and the reactive values its widgets share."""

    session: StudioSession
    revision: solara.Reactive[int]
    playing: solara.Reactive[bool]
    error: solara.Reactive[str | None]
    interval_ms: solara.Reactive[int]
    drawn: threading.Event

    def bump(self) -> None:
        """Tell every view the session changed."""
        self.revision.value += 1

    def act(self, call: Callable[..., Any], *args: Any) -> bool:
        """Run ``call(*args)``; on an exception, log it, stop playing and return False."""
        try:
            call(*args)
        except Exception as error:  # a model error is shown, not raised into the UI
            message = f"{type(error).__name__}: {error}"
            self.session.say(f"error: {message}")
            self.session.say(traceback.format_exc(limit=-1).strip())
            self.error.value = message
            self.playing.value = False
            return False
        else:
            self.error.value = None
            return True
        finally:
            self.bump()


def use_studio_state(session: StudioSession) -> StudioState:
    """The state of one Studio page (a hook: call it once, at the top of the page)."""
    return StudioState(
        session=session,
        revision=solara.use_reactive(0),
        playing=solara.use_reactive(False),
        error=solara.use_reactive(None),
        interval_ms=solara.use_reactive(DEFAULT_INTERVAL_MS),
        drawn=solara.use_memo(threading.Event, []),
    )
