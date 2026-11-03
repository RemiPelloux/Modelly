"""One model on the hub: what it is, where its code is, how it was validated, how to cite it.

An index (``index.json``) is ``{"schema": 1, "models": [entry, ...]}``. An entry names the
model (``name``, ``title``, ``field``, ``summary``, ``keywords``), its ``version``, the
``target`` to build it (``package.module:Class``), where its code comes from (``source``), the
Modelly versions it supports (``modelly``), its model card, and optionally a DOI, a run
bundle to verify and a Sigstore signature. ``kind`` is ``"zoo"`` for a model shipped inside
Modelly, ``"package"`` for one installed from a URL or from PyPI.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from typing import Any

SCHEMA = 1
KINDS = ("zoo", "package")
NAME = re.compile(r"^[a-z][a-z0-9_]*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REQUIRED = ("name", "title", "field", "summary", "version", "kind", "target", "modelly")


class EntryError(ValueError):
    """An index entry that does not follow the schema; the message says what is wrong."""


@dataclass(frozen=True)
class Source:
    """Where the model's code comes from.

    Attributes:
        requirement: what pip installs (``"modelly-abm>=1.5"``, ``"seir-plus==1.0"``).
        url: a wheel or sdist to download instead of the index, or None.
        sha256: the file's hash, required with ``url``.
    """

    requirement: str
    url: str | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class Artifact:
    """A file the entry points to (a run bundle, a signature), with its hash.

    Attributes:
        url: where to download it.
        sha256: its hash.
        identity, issuer: for a Sigstore signature, the signer's identity and its OIDC
            issuer, which verification requires.
    """

    url: str
    sha256: str
    identity: str = ""
    issuer: str = ""


@dataclass(frozen=True)
class HubEntry:
    """A model on the hub; see the module docstring for the fields."""

    name: str
    title: str
    field: str
    summary: str
    version: str
    kind: str
    target: str
    modelly: str
    source: Source
    keywords: tuple[str, ...] = ()
    authors: tuple[str, ...] = ()
    license: str = ""
    card: dict[str, Any] = field(default_factory=dict)
    doi: str | None = None
    bundle: Artifact | None = None
    signature: Artifact | None = None

    def to_dict(self) -> dict[str, Any]:
        """The entry as JSON-ready data, without empty optional fields."""
        data = asdict(self)
        data["keywords"], data["authors"] = list(self.keywords), list(self.authors)
        return _pruned(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HubEntry:
        """An entry from index data, checked.

        Raises:
            EntryError: when a field is missing, unknown or malformed.
        """
        problems = check(data)
        if problems:
            raise EntryError(f"entry {data.get('name', '?')!r}: " + "; ".join(problems))
        known = {f.name for f in fields(cls)}
        values = {k: v for k, v in data.items() if k in known}
        values["source"] = Source(**data["source"])
        for key in ("bundle", "signature"):
            if data.get(key):
                values[key] = Artifact(**data[key])
        values["keywords"] = tuple(data.get("keywords", ()))
        values["authors"] = tuple(data.get("authors", ()))
        return cls(**values)


def _pruned(data: dict[str, Any]) -> dict[str, Any]:
    """``data`` without empty optional fields, in nested tables too (not inside the card)."""
    out = {}
    for key, value in data.items():
        kept = _pruned(value) if isinstance(value, dict) and key != "card" else value
        if kept not in (None, "", [], {}):
            out[key] = kept
    return out


def check(data: dict[str, Any]) -> list[str]:
    """Every way ``data`` breaks the entry schema; empty when it is a valid entry."""
    found = [f"missing {key}" for key in REQUIRED if not data.get(key)]
    known = {f.name for f in fields(HubEntry)}
    found += [f"unknown field {key}" for key in sorted(set(data) - known)]
    if data.get("name") and not NAME.match(data["name"]):
        found.append("name must be lower case letters, digits and underscores")
    if data.get("kind") and data["kind"] not in KINDS:
        found.append(f"kind must be one of {KINDS}")
    if ":" not in str(data.get("target", ":")):
        found.append("target must be package.module:Class")
    found += _check_source(data.get("source"))
    for key in ("bundle", "signature"):
        if data.get(key) and not SHA256.match(str(data[key].get("sha256", ""))):
            found.append(f"{key} needs a sha256")
    return found


def _check_source(source: Any) -> list[str]:
    """Problems of the ``source`` table."""
    if not isinstance(source, dict) or not source.get("requirement"):
        return ["source needs a requirement"]
    if source.get("url") and not SHA256.match(str(source.get("sha256", ""))):
        return ["a source url needs its sha256"]
    return []
