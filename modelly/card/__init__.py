"""Model cards: what a model is for, how it was validated, and where it must not be used.

A card is a ``card.toml`` next to the model (``modelly.card.schema``), with sections for
intended use, out-of-scope use, data, validation, known limits and ethical considerations.
``card_skeleton`` writes a new one from the model's code; ``problems`` reports a card that
is incomplete or *stale* (the model changed since its validation tests last passed), and
``stamp`` runs those tests and records the source they passed on. Every zoo model has one:
``modelly card show age_seir``. Guide: ``docs/model_cards.md``.
"""

from modelly.card.freshness import problems, source_digest, stamp
from modelly.card.render import card_markdown, card_skeleton
from modelly.card.schema import (
    CardError,
    Check,
    ModelCard,
    Stamp,
    card_toml,
    read_card,
    write_card,
)

__all__ = [
    "CardError",
    "Check",
    "ModelCard",
    "Stamp",
    "card_markdown",
    "card_skeleton",
    "card_toml",
    "problems",
    "read_card",
    "source_digest",
    "stamp",
    "write_card",
]
