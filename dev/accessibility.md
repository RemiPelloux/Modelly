# Accessibility and languages

Modelly Studio and this documentation aim at [WCAG 2.2](https://www.w3.org/TR/WCAG22/) level AA: usable with a keyboard and a screen reader, readable at 200% zoom, with text contrast of at least 4.5:1, and in more than one language.

## How it is checked

`scripts/release-checks.sh a11y` runs [axe-core](https://github.com/dequelabs/axe-core), the standard automated WCAG checker, in Chromium. It checks every rule tagged WCAG 2.0, 2.1 and 2.2, levels A and AA, on:

- the home page, the getting-started page and its French translation;
- a zoo page, the Studio, Decisions and What’s new guides, and the course;
- Studio itself, in English, in French in no-code mode, and in Arabic (right to left), after a step has run, so the plots are drawn.

Any violation fails the stage, and the stage runs before every release. An automated checker finds only part of the accessibility problems a person meets: it cannot judge whether a screen reader’s reading order makes sense or whether a task can be finished with the keyboard alone. Those passes need people who use these tools; please [report](https://github.com/RemiPelloux/Modelly/issues) anything that gets in your way.

## What Studio does

- **Zoom.** The page can be zoomed and scaled (Solara’s page template turned that off).
- **Names.** Every slider is named after its field and every icon button after its icon. Every plot has alternative text from its panel’s title, so a screen reader says what each control and figure is.
- **Contrast and focus.** Field labels, the top bar and the status bar meet 4.5:1. The keyboard focus is a visible 3-pixel ring in Okabe-Ito blue.
- **Colour.** Agents and series use the Okabe-Ito palette, which stays distinct for the common forms of colour blindness, by default.
- **Language.** `modelly studio model.py:Model --language fr` shows every label in French; `es`, `pt` and `zh` are also shipped. The page declares its language to screen readers. Arabic, Hebrew, Persian and Urdu turn the page right to left; their catalogs are not written yet, so their labels are in English.

The layer lives in `modelly/templates/index.html.j2`, which Solara finds before its own page template, and `modelly/studio/a11y.py`.

## Languages

Language

Studio

Getting started

English

yes

[yes](https://remipelloux.github.io/Modelly/dev/getting_started.html)

Français

--language fr

[oui](https://remipelloux.github.io/Modelly/dev/translations/fr/getting_started.html)

Español

--language es

[sí](https://remipelloux.github.io/Modelly/dev/translations/es/getting_started.html)

Português

--language pt

[sim](https://remipelloux.github.io/Modelly/dev/translations/pt/getting_started.html)

中文

--language zh

[是](https://remipelloux.github.io/Modelly/dev/translations/zh/getting_started.html)

The translations were drafted for 1.5 and are open to review by native speakers: corrections are welcome as pull requests. A Studio catalog is a JSON file in `modelly/studio/locales/`, keyed by the English label. `tests/studio/test_studio_i18n.py` fails when a label in the code is missing from a catalog, so a new label is translated in the same change.
