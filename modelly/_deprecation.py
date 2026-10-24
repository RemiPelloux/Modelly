"""The one way Modelly deprecates something: ``deprecated(name, replacement)``.

Policy (``docs/deprecations.md``): a deprecated name keeps working and warns for at
least one minor release; the warning names the replacement and the version that
removes it; removals happen only in a major release (2.0).

Example:
    >>> import warnings
    >>> with warnings.catch_warnings(record=True) as caught:
    ...     warnings.simplefilter("always")
    ...     deprecated("old_name()", "new_name()")
    >>> str(caught[0].message)
    'old_name() is deprecated and will be removed in Modelly 2.0; use new_name() instead.'
"""

from __future__ import annotations

import warnings

REMOVAL = "2.0"
# The first release that may remove a deprecated name: removals are major-only.
FIRST_REMOVAL_MAJOR = 2
_HELPER_FRAMES = 1  # this function's own frame, skipped by stacklevel


class ModellyDeprecationWarning(DeprecationWarning, FutureWarning):
    """A Modelly name that will be removed; the message names its replacement.

    A ``DeprecationWarning``, so ``python -W error::DeprecationWarning`` turns every one
    into an error, and a ``FutureWarning``, so code that filtered the warnings Modelly
    1.2 raised keeps working.
    """


def _major(version: str) -> int:
    return int(version.split(".", maxsplit=1)[0])


def deprecated(
    name: str, replacement: str, removal: str = REMOVAL, *, stacklevel: int = 2
) -> None:
    """Warn that ``name`` is deprecated in favour of ``replacement``.

    Args:
        name: what is deprecated, as the user wrote it (``"render(agent_portrayal=...)"``).
        replacement: what to use instead.
        removal: the release that removes ``name``; a major release.
        stacklevel: as for ``warnings.warn``, counted from the caller of this function.

    Raises:
        ValueError: without a replacement, or with a removal before 2.0.
    """
    if not replacement:
        raise ValueError(f"deprecating {name} needs a replacement to name")
    if _major(removal) < FIRST_REMOVAL_MAJOR:
        raise ValueError(f"removals happen in a major release, not {removal}")
    warnings.warn(
        f"{name} is deprecated and will be removed in Modelly {removal}; "
        f"use {replacement} instead.",
        ModellyDeprecationWarning,
        stacklevel=stacklevel + _HELPER_FRAMES,
    )
