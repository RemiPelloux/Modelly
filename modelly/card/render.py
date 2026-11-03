"""A card as Markdown, and the skeleton of a new card for a model class."""

from __future__ import annotations

import inspect

from modelly.card.schema import SECTIONS, TODO, Check, ModelCard

PROMPTS = {
    "intended_use": "the questions this model is built to answer, and for whom",
    "out_of_scope": "uses the model is not fit for (forecasting a real outbreak, ...)",
    "data": "the data the model or its defaults come from, or that it uses none",
    "limits": "assumptions and regimes where the results stop being trustworthy",
    "ethics": "who could be affected by decisions taken with it, and how",
}


def _bullets(items: tuple[str, ...]) -> list[str]:
    """A Markdown list."""
    return [f"- {item}" for item in items]


def _stamp_line(card: ModelCard) -> str:
    """Where and when the validation last passed."""
    if card.validated is None:
        return "**Validated:** not yet"
    stamp = card.validated
    return (
        f"**Validated:** {stamp.date} with Modelly {stamp.modelly}, on source "
        f"`{stamp.source.partition(':')[2][:12]}`"
    )


def card_markdown(card: ModelCard, level: int = 2, *, references: bool = True) -> str:
    """The card as Markdown, its title at heading ``level``, sections one level below.

    ``references=False`` leaves the references out, for a page that lists them already.
    """
    top, sub = "#" * level, "#" * (level + 1)
    lines = [f"{top} Model card: {card.title}", "", card.summary, ""]
    lines += [f"**Model:** `{card.model}` · {_stamp_line(card)}", ""]
    for key, heading in SECTIONS[:3]:
        lines += [f"{sub} {heading}", "", *_bullets(getattr(card, key)), ""]
    lines += [f"{sub} Validation", "", "| Check | Test |", "|---|---|"]
    lines += [
        f"| {c.check.replace('|', r'\|')} | `{c.test}` |" for c in card.validation
    ]
    lines.append("")
    for key, heading in SECTIONS[3:]:
        lines += [f"{sub} {heading}", "", *_bullets(getattr(card, key)), ""]
    if references and card.references:
        lines += [f"{sub} References", "", *_bullets(card.references), ""]
    return "\n".join(lines)


def card_skeleton(model_class: type, name: str | None = None) -> ModelCard:
    """A new card for ``model_class``: what the code tells, ``TODO`` for the rest."""
    doc = inspect.getdoc(model_class) or ""
    summary = doc.split("\n\n", 1)[0].replace("\n", " ") or f"{TODO}: one sentence."
    target = f"{model_class.__module__}:{model_class.__qualname__}"
    return ModelCard(
        name=name or model_class.__name__.lower(),
        title=model_class.__name__,
        model=target,
        summary=summary,
        **{key: (f"{TODO}: {PROMPTS[key]}.",) for key, _ in SECTIONS},
        validation=(Check(f"{TODO}: the result the test compares with", "tests/"),),
    )
