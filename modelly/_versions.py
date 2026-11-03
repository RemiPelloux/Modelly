"""Version specifiers, enough to read a plugin's requirement on ``modelly-abm``.

A plugin declares the Modelly versions it works with the standard way, as a dependency:
``dependencies = ["modelly-abm>=1.5,<2"]``. ``requirement_on`` finds that entry in a
distribution's ``Requires-Dist`` metadata and ``satisfies`` checks a version against it.
Release segments are compared as numbers; a pre-release (``1.5.0a1``, ``1.5.0rc1``) or a
development version sorts before its release, as in PEP 440, and a ``.postN`` after it.
"""

from __future__ import annotations

import re

_VERSION = re.compile(r"^\s*v?(\d+(?:\.\d+)*)(?:[.-]?(a|b|rc|dev|post)\.?(\d*))?", re.I)
_CLAUSE = re.compile(r"^\s*(~=|===|==|!=|<=|>=|<|>)\s*([^\s,;]+)\s*$")
_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*\(?([^;)]*)\)?")
# Ranks of the suffixes: development and pre-releases before the release, post after.
_RANK = {"dev": -4, "a": -3, "b": -2, "rc": -1, "": 0, "post": 1}


def _key(version: str, width: int) -> tuple[int, ...]:
    """A sortable key: the release padded to ``width`` numbers, then the suffix."""
    match = _VERSION.match(version)
    if match is None:
        raise ValueError(f"not a version: {version!r}")
    release = [int(part) for part in match.group(1).split(".")]
    release += [0] * (width - len(release))
    suffix = (match.group(2) or "").lower()
    return (*release, _RANK[suffix], int(match.group(3) or 0))


def _compare(version: str, op: str, bound: str) -> bool:
    """``version op bound`` for one clause."""
    if bound.endswith(".*"):
        prefix = bound[:-2].split(".")
        same = version.split(".")[: len(prefix)] == prefix
        return same if op == "==" else not same
    width = max(version.count("."), bound.count(".")) + 1
    a, b = _key(version, width), _key(bound, width)
    if op == "~=":
        head = bound.split(".")[:-1]
        return a >= b and version.split(".")[: len(head)] == head
    return {
        "==": a == b, "===": version == bound, "!=": a != b,
        "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b,
    }[op]  # fmt: skip


def satisfies(version: str, specifier: str) -> bool:
    """Whether ``version`` meets every clause of ``specifier`` (``">=1.5,<2"``).

    Example:
        >>> satisfies("1.5.0", ">=1.5,<2"), satisfies("2.0.0", ">=1.5,<2")
        (True, False)
        >>> satisfies("1.5.0rc1", ">=1.5")
        False
    """
    for clause in filter(str.strip, specifier.split(",")):
        match = _CLAUSE.match(clause)
        if match is None:
            raise ValueError(f"not a version clause: {clause!r}")
        if not _compare(version, *match.groups()):
            return False
    return True


def _normal(name: str) -> str:
    """A distribution name as PEP 503 compares them."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_on(requires: list[str] | None, name: str) -> str | None:
    """The specifier a ``Requires-Dist`` list puts on ``name`` (``""`` for any version).

    None when ``name`` is not required at all. Entries behind an ``extra ==`` marker are
    optional and skipped.
    """
    for entry in requires or ():
        if "extra ==" in entry.partition(";")[2].replace("  ", " "):
            continue
        match = _NAME.match(entry)
        if match and _normal(match.group(1)) == _normal(name):
            return match.group(3).strip()
    return None
