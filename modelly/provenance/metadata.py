"""Archive metadata stubs for a bundle: Zenodo's ``.zenodo.json`` and ``CITATION.cff``.

Both are generated from the manifest and leave ``TODO`` where only the authors know the
answer (title, creators, licence choice). Edit them before uploading the bundle.
"""

from __future__ import annotations

MODELLY_URL = "https://github.com/RemiPelloux/Modelly"
CFF_VERSION = "1.2.0"
DEFAULT_LICENSE = "cc-by-4.0"
KEYWORDS = ("agent-based model", "Modelly", "reproducibility")


def _summary(manifest: dict) -> str:
    """One sentence naming the model, the run and the Modelly build."""
    target = manifest["target"]
    run = manifest["run"]
    build = manifest["environment"]["modelly"]
    return (
        f"Outputs of {target['class']} ({target['source']}) run for {run['steps']} "
        f"step(s) with seed {run['seed']} on Modelly {build['version']} "
        f"({build['build']}). Rerun and compare with: modelly verify manifest.json"
    )


def zenodo_metadata(manifest: dict) -> dict:
    """The ``.zenodo.json`` deposit metadata, with TODO markers to fill in."""
    return {
        "creators": [{"affiliation": "TODO", "name": "TODO: Family name, Given names"}],
        "description": f"TODO: what the study shows. {_summary(manifest)}",
        "keywords": list(KEYWORDS),
        "license": DEFAULT_LICENSE,
        "notes": "TODO: check the licence; the bundle holds code and data.",
        "related_identifiers": [
            {
                "identifier": MODELLY_URL,
                "relation": "requires",
                "resource_type": "software",
            }
        ],
        "title": f"TODO: study title ({manifest['target']['class']})",
        "upload_type": "dataset",
    }


def citation_cff(manifest: dict) -> str:
    """A ``CITATION.cff`` stub for the study that cites Modelly as a reference."""
    version = manifest["environment"]["modelly"]["version"]
    return (
        f"cff-version: {CFF_VERSION}\n"
        'message: "If you use this study, please cite it as below."\n'
        'title: "TODO: study title"\n'
        "type: dataset\n"
        "authors:\n"
        '  - family-names: "TODO"\n'
        '    given-names: "TODO"\n'
        f'abstract: "{_summary(manifest)}"\n'
        "references:\n"
        "  - type: software\n"
        '    title: "Modelly"\n'
        f'    version: "{version}"\n'
        f'    url: "{MODELLY_URL}"\n'
    )
