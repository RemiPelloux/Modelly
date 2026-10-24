"""The tool panels: profiler, lint and the run log."""

from __future__ import annotations

import solara

from modelly.lint.explain import explain
from modelly.studio.state import StudioState

LOG_SHOWN = 50


@solara.component
def ProfilerPanel(state: StudioState):
    """``modelly profile`` over the last steps: top operations, us per agent, hints."""
    state.revision.get()
    session = state.session
    report = session.profile_report()
    with solara.Card(f"Profiler (last {session.config.profile_steps} steps)"):
        solara.Preformatted(report)


@solara.component
def LintPanel(state: StudioState):
    """``modelly lint`` on the model's file; a finding shows its explanation."""
    session = state.session
    checks = solara.use_reactive(0)
    findings = solara.use_memo(session.lint, [checks.value])
    chosen = solara.use_reactive(None)
    path = session.source_file()
    with solara.Card(f"Lint: {path.name if path else 'no source file'}"):
        solara.Button("Check again", on_click=lambda: checks.set(checks.value + 1))
        if not findings:
            solara.Success("No findings.")
        for finding in findings:
            label = f"line {finding.line}: {finding.rule.code} {finding.rule.message}"
            solara.Button(
                label,
                text=True,
                on_click=lambda code=finding.rule.code: chosen.set(code),
            )
        if chosen.value:
            solara.Preformatted(explain(chosen.value))


@solara.component
def LogPanel(state: StudioState):
    """The run log, newest last."""
    state.revision.get()
    lines = list(state.session.log)[-LOG_SHOWN:]
    with solara.Card("Run log"):
        solara.Preformatted("\n".join(lines) or "(empty)")
