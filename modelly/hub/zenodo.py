"""Archiving a hub package on Zenodo, for a DOI, through Zenodo's deposit API.

``Zenodo(token).deposit(files, metadata)`` creates a deposition, uploads the files to its
bucket, sets the metadata and publishes it, returning the DOI and the files' URLs. The token
is read from ``ZENODO_TOKEN`` by the command line and is never written anywhere. ``sandbox``
(the default of the command line) uses sandbox.zenodo.org, whose DOIs are not real, to try a
publication first. ``DryRun`` is a transport that sends nothing and records the requests, so
a dry run shows exactly what would be sent.

Reference: https://developers.zenodo.org/ (REST API, depositions and bucket uploads).
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

PRODUCTION, SANDBOX = "https://zenodo.org", "https://sandbox.zenodo.org"
TOKEN_ENVIRONMENT = "ZENODO_TOKEN"  # noqa: S105 - the variable's name, not a token
TIMEOUT_SECONDS = 120


class Transport(Protocol):
    """Sends one request and returns the decoded JSON reply."""

    def __call__(self, method: str, url: str, token: str, body: bytes | None,
                 content_type: str) -> dict[str, Any]:  # fmt: skip
        """Send ``method url`` with ``body``, authorised by ``token``."""


def http(
    method: str, url: str, token: str, body: bytes | None, content_type: str
) -> dict:
    """The real transport, over HTTPS."""
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", content_type)
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as reply:
        text = reply.read().decode("utf-8")
    return json.loads(text) if text else {}


@dataclass
class DryRun:
    """A transport that sends nothing: it records each request and answers like Zenodo."""

    requests: list[tuple[str, str, int]] = field(default_factory=list)

    def __call__(self, method, url, token, body, content_type) -> dict[str, Any]:
        """Record ``(method, url, bytes)``; a plausible reply."""
        self.requests.append((method, url, len(body or b"")))
        if url.endswith("/depositions") and method == "POST":
            return {
                "id": 0,
                "links": {"bucket": f"{url.rsplit('/api', 1)[0]}/api/files/dry-run"},
            }
        if url.endswith("/actions/publish"):
            return {"id": 0, "doi": "10.5281/zenodo.0"}
        return {}


@dataclass(frozen=True)
class Deposit:
    """A published deposition: its DOI and the URL of each file, by name."""

    doi: str
    record: str
    files: dict[str, str]


def metadata(title: str, description: str, version: str, authors: Sequence[str],
             keywords: Sequence[str], license_id: str) -> dict[str, Any]:  # fmt: skip
    """Zenodo metadata for a software deposit."""
    data = {
        "title": title, "upload_type": "software", "description": description,
        "version": version, "creators": [{"name": a} for a in authors or ["Unknown"]],
        "keywords": list(keywords),
    }  # fmt: skip
    if license_id:
        data["license"] = license_id
    return data


@dataclass
class Zenodo:
    """A client of one Zenodo instance with one token."""

    token: str
    sandbox: bool = True
    transport: Transport = http

    @property
    def base(self) -> str:
        """The instance's address."""
        return SANDBOX if self.sandbox else PRODUCTION

    def deposit(self, files: Sequence[Path], meta: dict[str, Any]) -> Deposit:
        """Create, upload, describe and publish; the DOI and the file URLs."""
        send = self.transport
        api = f"{self.base}/api/deposit/depositions"
        created = send("POST", api, self.token, b"{}", "application/json")
        bucket, ident = created["links"]["bucket"], created["id"]
        for path in files:
            send("PUT", f"{bucket}/{path.name}", self.token, path.read_bytes(),
                 "application/octet-stream")  # fmt: skip
        body = json.dumps({"metadata": meta}).encode("utf-8")
        send("PUT", f"{api}/{ident}", self.token, body, "application/json")
        published = send("POST", f"{api}/{ident}/actions/publish", self.token, None,
                         "application/json")  # fmt: skip
        record = f"{self.base}/records/{published.get('id', ident)}"
        urls = {path.name: f"{record}/files/{path.name}" for path in files}
        return Deposit(published["doi"], record, urls)
