"""The model card file: ``card.toml``, read and written without a TOML library to install.

A card is a short TOML file next to the model: what the model is for, what it must not be
used for, its data, how it was validated, its known limits and ethical considerations, and
a stamp recording which source the validation last passed on. Reading uses ``tomllib``;
writing produces the same layout every time, so a card regenerated without a change is the
same file.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA = 1
TODO = "TODO"
# (field, heading): the sections every card fills, in the order they are rendered.
SECTIONS = (
    ("intended_use", "Intended use"),
    ("out_of_scope", "Out-of-scope use"),
    ("data", "Data"),
    ("limits", "Known limits"),
    ("ethics", "Ethical considerations"),
)


class CardError(ValueError):
    """A card file that cannot be read: bad TOML, a missing key or an unknown schema."""


@dataclass(frozen=True)
class Check:
    """One validation: what it checks and the test that checks it.

    Attributes:
        check: the claim, in a sentence ("attack rate against the final-size relation").
        test: the pytest target that checks it, relative to the project root
            (``tests/test_validation.py`` or ``tests/test_x.py::test_y``).
    """

    check: str
    test: str


@dataclass(frozen=True)
class Stamp:
    """When validation last passed: on which source, with which Modelly, on which date.

    Attributes:
        source: ``sha256:<hex>`` of the model's source files (``freshness.source_digest``).
        modelly: the Modelly version the validation ran with.
        date: the date it passed, ``YYYY-MM-DD``.
    """

    source: str
    modelly: str
    date: str


@dataclass(frozen=True)
class ModelCard:
    """A model card; see ``docs/model_cards.md`` for what each section holds.

    Attributes:
        name: a short identifier (the zoo name, or the project's).
        title: a human-readable title.
        model: the model class, ``package.module:Class``.
        summary: one or two sentences.
        intended_use: the questions the model answers, a list of statements.
        out_of_scope: the uses it is not fit for.
        data: the data behind its defaults and inputs.
        limits: its assumptions and where its results stop holding.
        ethics: who decisions taken with it could affect.
        validation: the checks and their tests.
        references: citations, one string each.
        sources: globs of the files whose change makes the validation stale, relative to
            the card's folder; empty means the model class's module.
        validated: the last passing validation, or None.
    """

    name: str
    title: str
    model: str
    summary: str
    intended_use: tuple[str, ...] = ()
    out_of_scope: tuple[str, ...] = ()
    data: tuple[str, ...] = ()
    limits: tuple[str, ...] = ()
    ethics: tuple[str, ...] = ()
    validation: tuple[Check, ...] = ()
    references: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    validated: Stamp | None = field(default=None)


LISTS = (*(name for name, _ in SECTIONS), "references", "sources")


def read_card(path: Path) -> ModelCard:
    """The card in ``path``.

    Raises:
        CardError: when the file is not TOML, lacks a required key, or has another schema.
    """
    try:
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as problem:
        raise CardError(f"{path}: {problem}") from problem
    if raw.get("schema") != SCHEMA:
        raise CardError(f"{path}: schema {raw.get('schema')!r}, expected {SCHEMA}")
    try:
        return _card(raw)
    except (KeyError, TypeError) as problem:
        raise CardError(f"{path}: missing or malformed {problem}") from problem


def _card(raw: dict[str, Any]) -> ModelCard:
    """A card from parsed TOML."""
    stamp = raw.get("validated")
    return ModelCard(
        name=raw["name"],
        title=raw["title"],
        model=raw["model"],
        summary=raw["summary"],
        **{key: tuple(raw.get(key, ())) for key in LISTS},
        validation=tuple(
            Check(c["check"], c["test"]) for c in raw.get("validation", ())
        ),
        validated=Stamp(stamp["source"], stamp["modelly"], stamp["date"])
        if stamp
        else None,
    )


def _string(text: str) -> str:
    """A TOML basic string (JSON's escapes are TOML's)."""
    return json.dumps(text, ensure_ascii=False)


def _list(name: str, items: tuple[str, ...]) -> list[str]:
    """``name = [...]``, one item per line."""
    if not items:
        return [f"{name} = []"]
    return [f"{name} = [", *(f"  {_string(item)}," for item in items), "]"]


def card_toml(card: ModelCard) -> str:
    """The card as TOML text, in a fixed layout."""
    lines = [f"schema = {SCHEMA}"]
    lines += [f"{key} = {_string(getattr(card, key))}" for key in ("name", "title", "model", "summary")]  # fmt: skip
    for key in LISTS:
        lines += ["", *_list(key, getattr(card, key))]
    for check in card.validation:
        lines += ["", "[[validation]]", f"check = {_string(check.check)}", f"test = {_string(check.test)}"]  # fmt: skip
    if card.validated is not None:
        stamp = card.validated
        lines += ["", "[validated]", f"source = {_string(stamp.source)}",
                  f"modelly = {_string(stamp.modelly)}", f"date = {_string(stamp.date)}"]  # fmt: skip
    return "\n".join(lines) + "\n"


def write_card(card: ModelCard, path: Path) -> None:
    """Write ``card`` to ``path`` with LF line endings."""
    Path(path).write_bytes(card_toml(card).encode("utf-8"))
