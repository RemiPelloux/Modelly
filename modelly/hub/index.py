"""Hub indexes: where they are, how they are read, and searching them.

The default index is the public one, ``DEFAULT_INDEX``. ``MODELLY_HUB`` (paths or URLs
separated by ``os.pathsep``) replaces it, for a private or a local index; installed packages
add more through the ``modelly.hub_sources`` entry-point group, each entry point naming a
URL string or a function returning one or several. An index is read over HTTPS or from a
file; the last copy read is cached, and used when the network is not there.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modelly.hub.entry import SCHEMA, HubEntry
from modelly.plugins import PluginError, discover

DEFAULT_INDEX = "https://remipelloux.github.io/modelly-hub/index.json"
ENVIRONMENT = "MODELLY_HUB"
SOURCES_GROUP = "modelly.hub_sources"
TIMEOUT_SECONDS = 20
CACHE_ENVIRONMENT = "MODELLY_CACHE"


class HubError(RuntimeError):
    """An index that cannot be read or does not follow the schema."""


def cache_dir() -> Path:
    """Where the hub caches indexes: ``MODELLY_CACHE``, or the platform's user cache."""
    if os.environ.get(CACHE_ENVIRONMENT):
        return Path(os.environ[CACHE_ENVIRONMENT]) / "hub"
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CACHE_HOME")
    return Path(base or Path.home() / ".cache") / "modelly" / "hub"


def _plugin_sources() -> list[str]:
    """The URLs the ``modelly.hub_sources`` plugins give; a broken one is skipped."""
    found: list[str] = []
    for plugin in discover(SOURCES_GROUP).values():
        try:
            value = plugin.load()
        except PluginError:
            continue
        value = value() if callable(value) else value
        found += [value] if isinstance(value, str) else list(value)
    return found


def sources() -> list[str]:
    """The indexes to read, in order: ``MODELLY_HUB`` or the default, then the plugins'."""
    configured = os.environ.get(ENVIRONMENT)
    first = (
        [s for s in configured.split(os.pathsep) if s]
        if configured
        else [DEFAULT_INDEX]
    )
    return first + _plugin_sources()


def _cached(source: str) -> Path:
    """The cache file of ``source``."""
    import hashlib  # noqa: PLC0415

    return cache_dir() / f"{hashlib.sha256(source.encode()).hexdigest()[:16]}.json"


def fetch(source: str) -> dict[str, Any]:
    """The index data at ``source`` (a path or a URL); the cached copy when offline.

    Raises:
        HubError: when it cannot be read and there is no cached copy, or is not an index.
    """
    try:
        if source.startswith(("http://", "https://")):
            with urllib.request.urlopen(source, timeout=TIMEOUT_SECONDS) as reply:
                text = reply.read().decode("utf-8")
            _cached(source).parent.mkdir(parents=True, exist_ok=True)
            _cached(source).write_text(text, encoding="utf-8")
        else:
            text = Path(source).read_text(encoding="utf-8")
    except OSError as problem:
        if not _cached(source).is_file():
            raise HubError(f"cannot read the index {source}: {problem}") from problem
        text = _cached(source).read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise HubError(f"{source} is not a hub index of schema {SCHEMA}")
    return data


@dataclass(frozen=True)
class Hub:
    """The models of every index read, the first index winning a name."""

    entries: tuple[HubEntry, ...]
    sources: tuple[str, ...]

    def get(self, name: str) -> HubEntry:
        """The entry called ``name``.

        Raises:
            KeyError: if no index has it.
        """
        for entry in self.entries:
            if entry.name == name:
                return entry
        raise KeyError(f"no model named {name!r} on the hub (modelly hub search)")


def load(where: list[str] | None = None) -> Hub:
    """Read the indexes ``where`` (by default ``sources()``) into one ``Hub``."""
    where = where if where is not None else sources()
    seen: dict[str, HubEntry] = {}
    for source in where:
        for data in fetch(source).get("models", []):
            entry = HubEntry.from_dict(data)
            seen.setdefault(entry.name, entry)
    return Hub(tuple(seen.values()), tuple(where))


def _score(entry: HubEntry, words: list[str]) -> int:
    """How well ``entry`` matches: name and keywords count most, the summary least."""
    weights = ((entry.name, 4), (" ".join(entry.keywords), 3), (entry.title, 2),
               (entry.field, 2), (entry.summary, 1))  # fmt: skip
    return sum(w for word in words for text, w in weights if word in text.lower())


def search(hub: Hub, query: str = "", field: str | None = None) -> list[HubEntry]:
    """The entries matching every word of ``query`` (and ``field``), best first."""
    words = query.lower().split()
    found = []
    for entry in hub.entries:
        if field is not None and entry.field != field:
            continue
        if all(_score(entry, [word]) for word in words):
            found.append((-_score(entry, words), entry.name, entry))
    return [entry for *_, entry in sorted(found)]
