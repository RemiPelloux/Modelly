"""Version specifiers for plugin declarations, as PEP 440 orders versions."""

import pytest

from modelly._versions import requirement_on, satisfies


@pytest.mark.parametrize(
    ("version", "specifier", "expected"),
    [
        ("1.5.0", ">=1.5,<2", True),
        ("1.5", ">=1.5.0", True),
        ("2.0.0", ">=1.5,<2", False),
        ("1.5.0rc1", ">=1.5", False),
        ("1.5.0a1", ">1.4.9", True),
        ("1.5.0.post1", ">1.5.0", True),
        ("1.5.0.dev0", "<1.5.0a1", True),
        ("1.5.3", "~=1.5.0", True),
        ("1.6.0", "~=1.5.0", False),
        ("1.6.0", "~=1.5", True),
        ("1.4.3", "==1.4.*", True),
        ("1.5.0", "!=1.5.0", False),
        ("1.5.0", "", True),
    ],
)
def test_satisfies(version, specifier, expected):
    """Each operator, pre-releases before their release and posts after it."""
    assert satisfies(version, specifier) is expected


def test_a_bad_clause_is_refused():
    """A clause without an operator is an error, not a silent pass."""
    with pytest.raises(ValueError, match="clause"):
        satisfies("1.5.0", "1.5")


def test_requirement_on_reads_requires_dist():
    """Names compare as PEP 503 normalises them; optional extras are skipped."""
    requires = ["numpy>=1.26", "modelly-abm[geo]>=1.5,<2; python_version >= '3.12'"]
    assert requirement_on(requires, "modelly_abm") == ">=1.5,<2"
    assert requirement_on(["modelly-abm"], "modelly-abm") == ""
    assert requirement_on(["modelly-abm>=1 ; extra == 'x'"], "modelly-abm") is None
    assert requirement_on(None, "modelly-abm") is None
