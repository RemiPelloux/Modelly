"""Studio in other languages: every label through ``t``, catalogs per language, right to left.

Each label Studio shows is written in English and passed through ``t(text)``, which returns
its translation in the session's language (``modelly studio --language fr``) from
``modelly/studio/locales/<language>.json``, or the English text when the catalog has none.
A language written right to left (Arabic, Hebrew, Persian, Urdu) also turns the page's
direction, so panels, tables and text line up from the right.

The catalogs are keyed by the English text. ``tests/studio/test_studio_i18n.py`` extracts
every ``t("...")`` from the code and checks that each shipped catalog translates exactly
those, so a new label without its translations fails the tests.
"""

from __future__ import annotations

import contextvars
import functools
import json
from importlib.resources import files

ENGLISH = "en"
RIGHT_TO_LEFT = frozenset({"ar", "he", "fa", "ur"})
_LANGUAGE: contextvars.ContextVar[str] = contextvars.ContextVar(
    "studio_language", default=ENGLISH
)


def languages() -> list[str]:
    """English and every language with a catalog, sorted."""
    folder = files(__package__).joinpath("locales")
    shipped = [
        p.name.removesuffix(".json")
        for p in folder.iterdir()
        if p.name.endswith(".json")
    ]
    return [ENGLISH, *sorted(shipped)]


@functools.cache
def catalog(language: str) -> dict[str, str]:
    """The translations of ``language``, keyed by the English text; empty for English.

    Raises:
        ValueError: for a language with no catalog.
    """
    if language == ENGLISH:
        return {}
    if language not in languages():
        raise ValueError(f"Studio speaks {languages()}, not {language!r}")
    text = files(__package__).joinpath("locales", f"{language}.json").read_text("utf-8")
    return dict(json.loads(text))


def set_language(language: str) -> None:
    """Translate the labels rendered from now on, in this context, into ``language``."""
    catalog(language)  # refuse an unknown language here, not at the first label
    _LANGUAGE.set(language)


def language() -> str:
    """The language labels are rendered in."""
    return _LANGUAGE.get()


def t(text: str) -> str:
    """``text`` in the current language, or as it is when there is no translation."""
    return catalog(_LANGUAGE.get()).get(text, text)


def direction(language_code: str | None = None) -> str:
    """``"rtl"`` for a language written right to left, ``"ltr"`` otherwise."""
    return "rtl" if (language_code or language()) in RIGHT_TO_LEFT else "ltr"
