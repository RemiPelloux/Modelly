"""Every zoo model has a model card, complete and validated on its current source."""

import pytest

from modelly.card import problems, read_card
from modelly.zoo.registry import MODELS


@pytest.mark.parametrize("entry", MODELS, ids=lambda entry: entry.name)
def test_every_zoo_model_has_a_fresh_card(entry):
    """The card names its model, fills every section and was stamped on this source.

    A change to a zoo model makes its card stale: run its validation again with
    ``modelly card stamp modelly/zoo/<name>/card.toml``.
    """
    card = read_card(entry.card)
    assert (card.name, card.title) == (entry.name, entry.title)
    assert card.model == f"{entry.module}:{entry.model}"
    assert problems(card, entry.card.parent) == []
