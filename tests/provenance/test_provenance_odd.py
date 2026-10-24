"""``odd``: the seven ODD elements, filled from the code, with TODO markers."""

from conftest import BOLTZMANN, SCHELLING

from modelly.profile.loader import build_model, load_class
from modelly.provenance import odd_markdown
from modelly.provenance.odd import DESIGN_CONCEPTS, SECTIONS


def _odd(target: str) -> str:
    """The ODD skeleton of a target built with seed 1."""
    return odd_markdown(build_model(load_class(target), {}, 1))


def test_seven_elements_in_order():
    """Each ODD element is a numbered section, in the protocol's order."""
    text = _odd(BOLTZMANN)
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == [f"## {i}. {title}" for i, title in enumerate(SECTIONS, start=1)]
    assert all(f"**{concept}**" in text for concept in DESIGN_CONCEPTS)
    assert "TODO" in text


def test_entities_from_columns_and_space():
    """MoneyAgent's wealth column, its count and the grid are described."""
    text = _odd(BOLTZMANN)
    assert "### MoneyAgent" in text
    assert "| `wealth` | `int64` | `1` |" in text
    assert "100 at initialization." in text
    assert "`OrthogonalMooreGrid`" in text


def test_schedule_and_submodels():
    """The step's statements in order, and each scheduled agent method."""
    text = _odd(SCHELLING)
    assert "2. `self.agents.shuffle_do('step')`" in text
    assert "Agent methods called: `step`, `assign_state`" in text
    assert "### SchellingAgent.assign_state" in text
    assert "| `density` | `0.8` | `0.8` |" in text
    assert "model: happy, pct_happy" in text
