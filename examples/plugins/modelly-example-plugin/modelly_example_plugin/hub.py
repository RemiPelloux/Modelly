"""A hub source: the index of a group's private models, read next to the public one.

``modelly hub search`` reads the public index, then every ``modelly.hub_sources`` entry
point: a URL or path string, or a function returning one or several. This example's index
lists no model; a lab would point it at its own ``index.json``.
"""

from __future__ import annotations

from pathlib import Path


def sources() -> list[str]:
    """The extra indexes this plugin adds."""
    return [str(Path(__file__).with_name("index.json"))]
