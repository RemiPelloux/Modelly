"""Upload the paper to Zenodo as a preprint: a draft by default, published with --publish.

    ZENODO_TOKEN=... python paper/submission/zenodo_upload.py             # draft, returns its URL
    ZENODO_TOKEN=... python paper/submission/zenodo_upload.py --publish   # mints the DOI
    ZENODO_TOKEN=... python paper/submission/zenodo_upload.py --sandbox   # sandbox.zenodo.org

The token is a Zenodo personal access token with the scopes deposit:write and
deposit:actions (Zenodo > Account > Applications > Personal access tokens). It is read from
the environment and never written anywhere. Publishing cannot be undone: a published record
and its DOI are permanent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDF = HERE.parent / "main.pdf"
TITLE = (
    "Modelly: Fast and Reproducible Agent-Based Modelling in Python, "
    "with Calibration and Sensitivity Analysis Built In"
)
KEYWORDS = [
    "agent-based modelling", "Python", "reproducibility",
    "approximate Bayesian computation", "global sensitivity analysis",
    "distributed simulation", "GPU", "data assimilation", "benchmarking",
    "scientific software",
]  # fmt: skip
RELATED = [
    {"identifier": "https://github.com/RemiPelloux/Modelly",
     "relation": "isSupplementedBy", "resource_type": "software"},
    {"identifier": "https://pypi.org/project/modelly-abm/1.4.2/",
     "relation": "isSupplementedBy", "resource_type": "software"},
    {"identifier": "swh:1:rel:661000598425e7a9b958b5a679ca1281aa6f6cc3",
     "relation": "isSupplementedBy", "resource_type": "software"},
]  # fmt: skip


def call(method: str, url: str, token: str, body: bytes | None = None,
         kind: str = "application/json") -> dict:  # fmt: skip
    """One authenticated request to the Zenodo API, its JSON answer."""
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        request.add_header("Content-Type", kind)
    with urllib.request.urlopen(request) as response:
        text = response.read()
    return json.loads(text) if text else {}


def metadata(orcid: str | None) -> dict:
    """The record's metadata: a CC BY 4.0 preprint by Rémi Pelloux."""
    creator = {"name": "Pelloux, Rémi", "affiliation": "OpenPro"}
    if orcid:
        creator["orcid"] = orcid
    return {"metadata": {
        "upload_type": "publication", "publication_type": "preprint",
        "title": TITLE, "creators": [creator],
        "description": (HERE / "abstract.txt").read_text(encoding="utf-8").strip(),
        "access_right": "open", "license": "cc-by-4.0", "language": "eng",
        "keywords": KEYWORDS, "related_identifiers": RELATED,
        "notes": "The author develops Modelly, the software evaluated in the paper.",
    }}  # fmt: skip


def main() -> int:
    """Create the deposition, upload the PDF, set the metadata, and publish if asked."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--sandbox", action="store_true")
    parser.add_argument("--orcid", default=None)
    options = parser.parse_args()
    token = os.environ.get("ZENODO_TOKEN") or sys.exit("set ZENODO_TOKEN")
    api = f"https://{'sandbox.' if options.sandbox else ''}zenodo.org/api"
    draft = call("POST", f"{api}/deposit/depositions", token, b"{}")
    call("PUT", f"{draft['links']['bucket']}/main.pdf", token, PDF.read_bytes(),
         "application/octet-stream")  # fmt: skip
    body = json.dumps(metadata(options.orcid)).encode()
    call("PUT", f"{api}/deposit/depositions/{draft['id']}", token, body)
    if not options.publish:
        print(f"draft saved: {draft['links']['html']}")
        return 0
    done = call("POST", f"{api}/deposit/depositions/{draft['id']}/actions/publish", token)
    print(f"published: DOI {done['doi']}  {done['links']['record_html']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
