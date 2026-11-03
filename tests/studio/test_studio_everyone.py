"""Studio for everyone: scenario comparison, reports, the model card, the builder, no-code."""

import itertools
import json
import subprocess
import sys

import pytest

solara = pytest.importorskip("solara")
v = pytest.importorskip("ipyvuetify")

from modelly.hub.publish import zoo_index  # noqa: E402
from modelly.new.builder import BEHAVIOURS, BuilderError, ModelSpec, build_code  # noqa: E402
from modelly.studio import __main__ as cli  # noqa: E402
from modelly.studio import app  # noqa: E402
from modelly.studio.compare import compare_scenarios  # noqa: E402
from modelly.studio.config import StudioConfig  # noqa: E402
from modelly.studio.everyone import comparison_rows, parse_values  # noqa: E402
from modelly.studio.report import markdown_html, report_html, report_pdf  # noqa: E402

BOLTZMANN = "modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"
SEIR = "modelly.zoo.age_seir.model:AgeSEIR"


def session(target=BOLTZMANN, **config):
    """A session of ``target``, run a few steps."""
    made = app.new_session(StudioConfig(target=target, **config))
    made.step(5)
    return made


def test_scenarios_compare_on_paired_replicates():
    """Three population sizes, five replicates: a row each, the first differs by zero."""
    found = compare_scenarios(session(), {f"n = {n}": {"n": n} for n in (20, 50, 100)}, "Gini",
                              steps=10, replicates=5)  # fmt: skip
    rows = comparison_rows(found, "Gini")
    assert {r["scenario"] for r in rows} == {"n = 20", "n = 50", "n = 100"}
    assert next(r for r in rows if r["scenario"] == "n = 20")["difference"] == "+0"
    with pytest.raises(ValueError, match="reporter"):
        compare_scenarios(session(), {"a": {}, "b": {}}, "nothing")
    assert parse_values("0.1, 2, abc") == [0.1, 2, "abc"]


def test_the_html_report_holds_figures_card_and_manifest():
    """A zoo model's report: parameters, an embedded figure per reporter, its card, the manifest."""
    text = report_html(session(SEIR))
    assert (
        text.startswith("<!doctype html>") and text.count("data:image/png;base64,") == 4
    )
    assert "Model card: Age-structured SEIR" in text and "Intended use" in text
    assert "Run manifest" in text and "source sha256" in text
    assert report_pdf(session(SEIR)).startswith(b"%PDF")


def test_card_markdown_becomes_html():
    """Headings, bullets, tables and paragraphs; text is escaped."""
    out = markdown_html(
        "## Title\n\nSome <b>text</b>.\n\n- one\n\n| A | B |\n|---|---|\n| 1 | `2` |\n"
    )
    assert "<h3>Title</h3>" in out and "&lt;b&gt;" in out and "<li>one</li>" in out
    assert "<th>A</th>" in out and "<td>2</td>" in out


@pytest.mark.parametrize(
    "behaviours",
    [c for n in range(1, 5) for c in itertools.combinations(BEHAVIOURS, n)],
    ids="+".join,
)
def test_every_built_model_runs_and_lints(tmp_path, behaviours):
    """Each combination of behaviours writes a model that runs and that modelly lint passes."""
    path = tmp_path / "built.py"
    path.write_text(
        build_code(ModelSpec(behaviours=behaviours, steps=5)), encoding="utf-8"
    )
    run = subprocess.run(
        [sys.executable, str(path)], capture_output=True, text=True, check=False
    )
    assert run.returncode == 0, run.stderr
    lint = subprocess.run([sys.executable, "-m", "modelly", "lint", str(path)],
                          capture_output=True, text=True, check=False)  # fmt: skip
    assert lint.returncode == 0, lint.stdout


@pytest.mark.parametrize(
    ("spec", "message"),
    [(ModelSpec(name="model"), "CapWords"), (ModelSpec(agent="Model"), "CapWords"),
     (ModelSpec(behaviours=("fly",)), "behaviours"), (ModelSpec(count=0), "at least")],
)  # fmt: skip
def test_bad_specs_are_refused(spec, message):
    """Each refusal says what to change."""
    with pytest.raises(BuilderError, match=message):
        build_code(spec)


def test_no_code_mode_keeps_the_tabs_for_everyone():
    """The developer tabs go; Compare, Card and Builder stay."""
    names = [name for name, _ in app.tabs_for("no-code")]
    assert {"Compare", "Card", "Builder", "Model"} <= set(names)
    assert not {"Profiler", "Lint", "Log", "Agents"} & set(names)
    assert len(app.tabs_for("full")) == len(app.all_tabs())


def test_hub_opens_a_model_by_name(tmp_path, monkeypatch, capsys):
    """--hub resolves the target from the index; giving both or neither is a usage error."""
    index = tmp_path / "index.json"
    index.write_text(json.dumps(zoo_index()), encoding="utf-8")
    monkeypatch.setenv("MODELLY_HUB", str(index))
    args = cli.build_parser().parse_args(["--hub", "age_seir", "--no-code"])
    config = cli.config_from(args)
    assert config.target == SEIR and config.mode == "no-code"
    assert cli.main([]) == 2
    assert "target or --hub" in capsys.readouterr().err


def test_the_compare_tab_runs_from_the_ui():
    """Type values, click Compare: the table appears."""
    rendered = solara.render(app.StudioApp(session()), handle_error=False)[1]
    tabs = rendered.find(v.Tabs).widget
    tabs.v_model = [name for name, _ in app.TABS].index("Compare")
    rendered.find(
        v.TextField, label="values to try, separated by commas"
    ).widget.v_model = "20, 40"
    rendered.find(v.Btn, children=["Compare"]).widget.click()
    assert "paired replicates" in " ".join(
        str(w.children) for w in rendered.find(v.Alert).widgets
    )
