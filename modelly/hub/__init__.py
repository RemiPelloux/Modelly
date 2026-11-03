"""The Modelly hub: published models, found and installed by name, cited by DOI.

The hub is a static index (``index.json``) in a public repository, served on GitHub Pages
and changed by pull request after automatic checks (``modelly.hub.check``); there is no
server. Each entry (``modelly.hub.entry``) carries the model's card, the Modelly versions it
supports, where its code is and its hash, and optionally a Zenodo DOI and a Sigstore
signature. ``modelly hub search``, ``info`` and ``install`` read the indexes
(``modelly.hub.index``); ``modelly hub publish`` writes a project's entry, archived on
Zenodo and signed when asked (``modelly.hub.publish``). Guide: ``docs/hub.md``.
"""

from modelly.hub.entry import Artifact, EntryError, HubEntry, Source
from modelly.hub.index import DEFAULT_INDEX, Hub, HubError, load, search, sources
from modelly.hub.install import install
from modelly.hub.publish import project_entry, publish, zoo_index

__all__ = [
    "DEFAULT_INDEX",
    "Artifact",
    "EntryError",
    "Hub",
    "HubEntry",
    "HubError",
    "Source",
    "install",
    "load",
    "project_entry",
    "publish",
    "search",
    "sources",
    "zoo_index",
]
