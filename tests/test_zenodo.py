"""The Zenodo metadata of the repository agrees with CITATION.cff and holds no contact data.

The GitHub-Zenodo integration archives every GitHub release and reads ``.zenodo.json``
instead of ``CITATION.cff`` when it is present, so the two must name the same work:
title, licence, keywords, and creators with their affiliations. The version is left out
on purpose: Zenodo takes it from the release tag.
"""

import json
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
ZENODO = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
CITATION = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
UPLOAD_TYPES = {"software"}


def _citation_creators() -> list[dict]:
    """CITATION.cff's authors in Zenodo's form: ``Family, Given`` or the name."""
    creators = []
    for author in CITATION["authors"]:
        if "family-names" in author:
            entry = {"name": f"{author['family-names']}, {author['given-names']}"}
            if "affiliation" in author:
                entry["affiliation"] = author["affiliation"]
        else:
            entry = {"name": author["name"]}
        creators.append(entry)
    return creators


def test_it_describes_the_same_work_as_citation_cff():
    """Title, licence, keywords and creators match the citation file."""
    assert ZENODO["title"] == CITATION["title"]
    assert ZENODO["license"] == CITATION["license"]
    assert ZENODO["keywords"] == CITATION["keywords"]
    assert ZENODO["creators"] == _citation_creators()
    assert ZENODO["description"] == " ".join(CITATION["abstract"].split())
    assert ZENODO["upload_type"] in UPLOAD_TYPES


def test_no_version_and_no_contact_data():
    """The release tag gives the version; no email address goes into the archive."""
    assert "version" not in ZENODO
    text = (ROOT / ".zenodo.json").read_text(encoding="utf-8")
    assert "@" not in text
    assert all(
        set(creator) <= {"name", "affiliation"} for creator in ZENODO["creators"]
    )
