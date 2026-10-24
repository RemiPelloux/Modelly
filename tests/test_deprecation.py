"""The deprecation policy: one helper, and every warning names a replacement and a removal.

``docs/deprecations.md`` is the policy. A deprecation warning raised anywhere in
``modelly/`` goes through ``modelly._deprecation.deprecated``, which refuses to warn
without a replacement or with a removal before 2.0; the scan below keeps it so.
"""

import ast
import warnings
from pathlib import Path

import pytest

import modelly
from modelly._deprecation import REMOVAL, ModellyDeprecationWarning, deprecated

PACKAGE = Path(modelly.__file__).parent
HELPER = PACKAGE / "_deprecation.py"
CATEGORIES = {"DeprecationWarning", "FutureWarning", "PendingDeprecationWarning"}


def test_message_names_replacement_and_removal():
    """The warning says what to use instead and which release removes the name."""

    def old():
        deprecated("old()", "new()")

    with pytest.warns(DeprecationWarning) as record:
        old()  # the warning points here, at the caller of the deprecated name
    message = str(record[0].message)
    assert message == (
        f"old() is deprecated and will be removed in Modelly {REMOVAL}; "
        "use new() instead."
    )
    assert record[0].filename == __file__


def test_category_is_a_deprecation_and_a_future_warning():
    """-W error::DeprecationWarning catches it; 1.2 FutureWarning filters still match."""
    assert issubclass(ModellyDeprecationWarning, DeprecationWarning)
    assert issubclass(ModellyDeprecationWarning, FutureWarning)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        with pytest.raises(ModellyDeprecationWarning):
            deprecated("old()", "new()")


def test_no_replacement_or_early_removal_is_refused():
    """A deprecation must name a replacement, and removals are major-only."""
    with pytest.raises(ValueError, match="replacement"):
        deprecated("old()", "")
    with pytest.raises(ValueError, match="major release"):
        deprecated("old()", "new()", removal="1.4")


def _deprecation_warnings(tree: ast.AST):
    """``warnings.warn``-style calls in ``tree`` whose category is a deprecation."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
        if "warn" in names and names & CATEGORIES:
            yield node.lineno


def test_every_deprecation_goes_through_the_helper():
    """No module but the helper raises a deprecation warning itself."""
    offenders = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if path == HELPER:
            continue
        tree = ast.parse(path.read_bytes(), filename=str(path))
        offenders += [
            f"{path.relative_to(PACKAGE)}:{line}"
            for line in _deprecation_warnings(tree)
        ]
    assert offenders == [], "use modelly._deprecation.deprecated: " + ", ".join(
        offenders
    )
