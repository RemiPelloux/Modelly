"""The Classroom tab: submit this run, share these parameters, see the class's runs."""

from __future__ import annotations

from typing import Any

import solara

from modelly.studio.classroom import share, submissions, submit
from modelly.studio.i18n import t


@solara.component
def ClassroomTab(state: Any):
    """Without ``--classroom`` it says how to start one; with it, the class's runs."""
    folder = state.session.config.classroom
    student, message = solara.use_reactive(""), solara.use_reactive("")
    revision = solara.use_reactive(0)
    with solara.Card(t("Classroom")):
        if folder is None:
            solara.Info(
                t("Start Studio with --classroom FOLDER to share runs with a class.")
            )
            return

        def send() -> None:
            try:
                submit(state.session, folder, student.value)
            except ValueError as error:
                message.set(str(error))
                return
            message.set(t("Run submitted."))
            revision.set(revision.value + 1)

        def publish() -> None:
            share(state.session, folder)
            message.set(t("Parameters shared: new sessions start from them."))

        solara.InputText(t("your name"), value=student, continuous_update=True)
        with solara.Row():
            solara.Button(t("Submit this run"), on_click=send)
            solara.Button(t("Share these parameters"), on_click=publish)
        if message.value:
            solara.Info(message.value)
        runs = submissions(folder)
        if len(runs):
            solara.DataFrame(runs)
