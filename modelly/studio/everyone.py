"""The Studio tabs for people who do not write code: compare, the model card, the builder.

* ``CompareTab``: pick a reporter, a parameter and the values to try; Studio runs each
  value on common random numbers (``modelly.studio.compare``) and shows the ranking with
  intervals and the differences from the first value.
* ``CardTab``: the model card, when the model has one.
* ``BuilderTab``: a form over ``modelly.new.builder``; it shows the model's code and
  downloads it.

``report_downloads`` adds the HTML and PDF reports to the Export panel. With
``modelly studio --no-code`` only these tabs and the views stay (``NO_CODE_TABS``).
"""

from __future__ import annotations

import ast
from typing import Any

import pandas as pd
import solara

from modelly.card import card_markdown, read_card
from modelly.new.builder import BEHAVIOURS, BuilderError, ModelSpec, build_code
from modelly.studio.compare import compare_scenarios, reporters
from modelly.studio.i18n import t
from modelly.studio.report import card_path, report_html, report_pdf

NO_CODE_TABS = (
    "Model",
    "Map",
    "Compare",
    "Card",
    "Builder",
    "Classroom",
    "Experiments",
)


def parse_values(text: str) -> list[Any]:
    """``"0.1, 0.2, 0.3"`` as Python values; a value that is not a literal stays a string."""
    values = []
    for part in (p.strip() for p in text.split(",")):
        if part:
            try:
                values.append(ast.literal_eval(part))
            except (ValueError, SyntaxError):
                values.append(part)
    return values


def comparison_rows(comparison: Any, output: str) -> list[dict[str, Any]]:
    """The table the Compare tab shows: one row per scenario, best first."""
    rank, diff = comparison.rank(output), comparison.difference(output)
    return [
        {"scenario": name, output: round(row["mean"], 4),
         "interval": f"{row['low']:.4g} to {row['high']:.4g}",
         "difference": f"{diff.loc[name, 'mean']:+.4g}", "lowest in": f"{row['best_share']:.0%}"}
        for name, row in rank.iterrows()
    ]  # fmt: skip


def run_comparison(
    session: Any, parameter: str, text: str, output: str, steps: int, replicates: int
) -> tuple[list[dict[str, Any]] | None, str]:
    """The Compare tab's table and message for ``parameter`` set to each value of ``text``."""
    values = parse_values(text) or [session.values.get(parameter)]
    scenarios = {f"{parameter} = {v}": {parameter: v} for v in values}
    try:
        found = compare_scenarios(
            session, scenarios, output, steps=steps, replicates=replicates
        )
    except (ValueError, TypeError) as error:
        return None, str(error)
    return comparison_rows(
        found, output
    ), f"{replicates} paired replicates of {steps} steps each"


@solara.component
def CompareTab(state: Any):
    """Vary one parameter, compare the scenarios with paired replicates."""
    session = state.session
    outputs = reporters(session) or ["(no reporter)"]
    names = sorted(session.values)
    output = solara.use_reactive(outputs[0])
    parameter = solara.use_reactive(names[0] if names else "")
    text = solara.use_reactive("")
    replicates, steps = solara.use_reactive(10), solara.use_reactive(50)
    result, message = solara.use_reactive(None), solara.use_reactive("")

    def run() -> None:
        rows, said = run_comparison(session, parameter.value, text.value, output.value,
                                    steps.value, replicates.value)  # fmt: skip
        result.set(rows)
        message.set(said)

    _compare_form(outputs, names, (output, parameter, text, replicates, steps), run)
    if message.value:
        solara.Info(message.value)
    if result.value:
        solara.DataFrame(pd.DataFrame(result.value))


def _compare_form(
    outputs: list[str], names: list[str], fields: tuple, run: Any
) -> None:
    """The Compare tab's form: output, parameter, values, replicates, steps, the button."""
    output, parameter, text, replicates, steps = fields
    with solara.Card(t("Compare scenarios")):
        solara.Select(t("output"), values=outputs, value=output)
        solara.Select(t("parameter"), values=names, value=parameter)
        solara.InputText(
            "values to try, separated by commas", value=text, continuous_update=True
        )
        solara.InputInt(t("replicates"), value=replicates)
        solara.InputInt(t("steps"), value=steps)
        solara.Button(t("Compare"), on_click=run)


@solara.component
def CardTab(state: Any):
    """The model card, or how to write one."""
    path = card_path(state.session.config.target)
    with solara.Card(t("Model card")):
        if path is None:
            solara.Info(
                "This model has no card yet: write one with `modelly card new`."
            )
        else:
            solara.Markdown(card_markdown(read_card(path)))


@solara.component
def BuilderTab(state: Any):
    """A model from a form: names, sizes, behaviours; its code to read and download."""
    name, agent = solara.use_reactive("Classroom"), solara.use_reactive("Student")
    count, width = solara.use_reactive(100), solara.use_reactive(20)
    chosen = solara.use_reactive(["walk"])
    with solara.Card(t("Model builder")):
        solara.InputText(t("model name"), value=name)
        solara.InputText(t("agent name"), value=agent)
        solara.InputInt(t("agents"), value=count)
        solara.InputInt(t("grid size"), value=width)
        solara.SelectMultiple(
            t("behaviours"), all_values=list(BEHAVIOURS), values=chosen
        )
        try:
            code = build_code(ModelSpec(name.value, agent.value, count.value, width.value,
                                        width.value, tuple(chosen.value)))  # fmt: skip
        except BuilderError as error:
            solara.Error(str(error))
            return
        solara.FileDownload(
            code.encode("utf-8"),
            f"{name.value.lower()}.py",
            label=t("Download model.py"),
        )
        solara.Markdown(f"```python\n{code}```")


def report_downloads(state: Any, stamp: str) -> list[tuple]:
    """``(make the bytes, file name, label)`` of the HTML and PDF reports."""
    session = state.session
    return [
        (
            lambda: report_html(session).encode("utf-8"),
            f"{stamp}-report.html",
            "Report (HTML)",
        ),
        (lambda: report_pdf(session), f"{stamp}-report.pdf", "Report (PDF)"),
    ]
