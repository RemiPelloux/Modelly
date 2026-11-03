"""Publishing to the hub: an entry for a project (or a zoo model), archived and signed.

``project_entry(folder)`` reads a project's ``pyproject.toml`` (``[project]`` and the
``[tool.modelly.hub]`` table: ``target`` and ``field``), its ``card.toml``, which must be
complete and validated on the current source, and its built wheel in ``dist/``.
``publish`` optionally signs the wheel (Sigstore) and archives it on Zenodo for a DOI, then
writes ``hub-entry.json``: the entry to add to the index by pull request.

``zoo_index()`` is the index of the zoo models, which are part of Modelly itself.
"""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

import modelly
from modelly._versions import release
from modelly.card import problems, read_card
from modelly.hub.entry import SCHEMA, Artifact, HubEntry, Source
from modelly.hub.index import HubError
from modelly.hub.install import sha256_of
from modelly.hub.sign import sign
from modelly.hub.zenodo import Zenodo, metadata
from modelly.zoo.registry import MODELS, ZooModel

ENTRY_FILE = "hub-entry.json"


def supported() -> str:
    """The specifier of this Modelly's minor version up to the next major: ``">=1.5,<2"``."""
    major, minor = modelly.__version__.split(".")[:2]
    return f">={major}.{minor},<{int(major) + 1}"


def zoo_entry(zoo: ZooModel) -> HubEntry:
    """The hub entry of a zoo model, its card included."""
    card = read_card(zoo.card)
    return HubEntry(
        name=zoo.name, title=zoo.title, field=zoo.field, summary=zoo.summary,
        version=release(modelly.__version__), kind="zoo", target=f"{zoo.module}:{zoo.model}",
        modelly=supported(), source=Source(f"modelly-abm{supported()}"),
        keywords=(zoo.field, *zoo.name.split("_")), license="Apache-2.0",
        authors=("Modelly contributors",), card=_card_data(card),
    )  # fmt: skip


def _card_data(card: Any) -> dict[str, Any]:
    """A card as plain JSON data."""
    data = asdict(card)
    data["validation"] = [asdict(check) for check in card.validation]
    return data


def zoo_index() -> dict[str, Any]:
    """The index of every zoo model."""
    return {"schema": SCHEMA, "models": [zoo_entry(zoo).to_dict() for zoo in MODELS]}


def _wheel(folder: Path) -> Path:
    """The newest wheel in ``folder/dist``."""
    wheels = sorted((folder / "dist").glob("*.whl"), key=lambda p: p.stat().st_mtime)
    if not wheels:
        raise HubError(f"no wheel in {folder / 'dist'}: run python -m build first")
    return wheels[-1]


def project_entry(folder: Path) -> tuple[HubEntry, Path]:
    """The entry of the project in ``folder`` and its wheel.

    Raises:
        HubError: without a ``[tool.modelly.hub]`` table, a fresh card or a wheel.
    """
    folder = Path(folder)
    project = tomllib.loads((folder / "pyproject.toml").read_text(encoding="utf-8"))
    meta, hub = (
        project["project"],
        project.get("tool", {}).get("modelly", {}).get("hub"),
    )
    if not hub or "target" not in hub or "field" not in hub:
        raise HubError("pyproject.toml needs [tool.modelly.hub] with target and field")
    card = read_card(folder / "card.toml")
    found = problems(card, folder)
    if found:
        raise HubError("the model card is not ready: " + "; ".join(found))
    wheel = _wheel(folder)
    entry = HubEntry(
        name=meta["name"].replace("-", "_").lower(), title=card.title, field=hub["field"],
        summary=card.summary, version=meta["version"], kind="package", target=hub["target"],
        modelly=hub.get("modelly", supported()),
        source=Source(f"{meta['name']}=={meta['version']}"),
        keywords=tuple(meta.get("keywords", ())), license=str(meta.get("license", "")),
        authors=tuple(a.get("name", "") for a in meta.get("authors", ())), card=_card_data(card),
    )  # fmt: skip
    return entry, wheel


@dataclass
class Published:
    """What ``publish`` did."""

    entry: HubEntry
    path: Path
    commands: list[list[str]] = field(default_factory=list)
    doi: str | None = None


@dataclass(frozen=True)
class Signer:
    """Who signs: the identity and OIDC issuer Sigstore will bind the signature to."""

    identity: str
    issuer: str = "https://github.com/login/oauth"


def publish(
    folder: Path, zenodo: Zenodo | None = None, signer: Signer | None = None,
    dry_run: bool = True,
) -> Published:  # fmt: skip
    """Write ``hub-entry.json``; sign the wheel and archive it on Zenodo when asked."""
    signed = signer is not None
    entry, wheel = project_entry(Path(folder))
    command, bundle = sign(wheel, dry_run=dry_run) if signed else ([], None)
    files = [wheel] + ([bundle] if bundle else [])
    doi = None
    if zenodo is not None:
        meta = metadata(entry.title, entry.summary, entry.version, entry.authors,
                        entry.keywords, entry.license)  # fmt: skip
        deposit = zenodo.deposit(files, meta)
        doi = deposit.doi
        source = replace(
            entry.source, url=deposit.files[wheel.name], sha256=sha256_of(wheel)
        )
        entry = replace(entry, source=source, doi=doi)
        if bundle is not None:
            signature = Artifact(deposit.files[bundle.name], sha256_of(bundle),
                                 signer.identity, signer.issuer)  # fmt: skip
            entry = replace(entry, signature=signature)
    path = Path(folder) / ENTRY_FILE
    import json  # noqa: PLC0415

    path.write_text(json.dumps(entry.to_dict(), indent=2) + "\n", encoding="utf-8")
    return Published(entry, path, [command] if command else [], doi)
