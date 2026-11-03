"""Studio's languages: every label translated in every catalog, right-to-left direction."""

import ast
import json
from pathlib import Path

import pytest

solara = pytest.importorskip("solara")
v = pytest.importorskip("ipyvuetify")

from modelly.studio import app, i18n  # noqa: E402
from modelly.studio.config import StudioConfig  # noqa: E402

STUDIO = Path(i18n.__file__).parent
BOLTZMANN = "modelly.examples.basic.boltzmann_wealth_model.model:BoltzmannWealth"


def labels() -> set[str]:
    """Every ``t("...")`` of the Studio code, and the tab names."""
    found = {name for name, _ in app.TABS}
    for path in STUDIO.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            called = (
                isinstance(node, ast.Call) and getattr(node.func, "id", None) == "t"
            )
            if called and node.args and isinstance(node.args[0], ast.Constant):
                found.add(node.args[0].value)
    return found


@pytest.mark.parametrize("language", ["es", "fr", "pt", "zh"])
def test_every_catalog_translates_exactly_the_labels(language):
    """No label missing, none left over, placeholders kept, no empty translation."""
    catalog = json.loads(
        (STUDIO / "locales" / f"{language}.json").read_text(encoding="utf-8")
    )
    assert set(catalog) == labels()
    assert all(text.strip() for text in catalog.values())
    assert "{steps}" in catalog["Run {steps}"]


def render(language):
    """Studio rendered in ``language``."""
    session = app.new_session(StudioConfig(target=BOLTZMANN, language=language))

    @solara.component
    def Served():
        with solara.AppLayout():
            app.StudioApp(session)

    return solara.render(Served(), handle_error=False)[1]


def test_studio_speaks_french_and_back_to_english():
    """The buttons and tabs follow the language; English is the default."""
    rendered = render("fr")
    french = i18n.catalog("fr")
    rendered.find(v.Btn, children=[french["Step"]]).assert_single()
    tabs = [str(t.children[0]) for t in rendered.find(v.Tab).widgets]
    assert french["Compare"] in tabs
    rendered = render("en")
    rendered.find(v.Btn, children=["Step"]).assert_single()


def test_right_to_left_languages_turn_the_page():
    """Arabic, Hebrew, Persian and Urdu read right to left; an unknown catalog is refused."""
    assert i18n.direction("ar") == "rtl" and i18n.direction("fr") == "ltr"
    with pytest.raises(ValueError, match="speaks"):
        i18n.set_language("xx")
    assert i18n.languages() == ["en", "es", "fr", "pt", "zh"]
