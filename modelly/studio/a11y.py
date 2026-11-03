"""Studio's accessibility layer (WCAG 2.2 AA), on top of Solara's page.

Solara's page template disables zooming and sets no language; Vuetify's sliders, icon
buttons and the plots' images carry no accessible names, and its field labels are lighter
than a 4.5:1 contrast. ``modelly/templates/index.html.j2``, which Solara finds before its own
template, re-enables zooming, raises the labels' contrast, shows a visible focus ring, and
runs a small script that names every unnamed slider (by its field's label), icon button (by
its icon) and image (by its card's title) as they appear, and sets the page's language and
direction from ``LanguageMarker``. ``tests/studio/test_studio_a11y.py`` runs axe-core on the
served page and on the documentation and fails on any WCAG A or AA violation.
"""

from __future__ import annotations

import solara

from modelly.studio.i18n import direction, language


@solara.component
def LanguageMarker():
    """An invisible element the page's script reads the language and direction from."""
    solara.HTML(
        tag="span",
        unsafe_innerHTML="",
        attributes={"data-modelly-language": language(), "data-modelly-direction": direction(),
                    "hidden": "hidden"},
    )  # fmt: skip
