"""Provenance and reproducible publication: manifests, verification, bundles and ODD.

``modelly run`` runs a model once and writes its collected data and a manifest that
records the code, environment, scenario, seeds, inputs, outputs and timing.
``modelly verify`` reruns a manifest and reports the first output that differs.
``modelly bundle`` packs a run into a deterministic zip for an archive such as Zenodo.
``modelly odd`` writes an ODD protocol skeleton from the model's code.

The same steps from Python::

    from modelly.provenance import RunSpec, bundle, run_study, verify

    run_study(RunSpec("model.py:Epidemic", out=Path("runs"), steps=100, seed=1))
    assert verify(Path("runs/manifest.json")).matches
    bundle(Path("runs"), Path("study.zip"))
"""

from modelly.provenance.bundle import BundleError, bundle
from modelly.provenance.compare import Difference, Tolerance, first_difference
from modelly.provenance.manifest import (
    FORMAT,
    MANIFEST_NAME,
    ManifestError,
    read_manifest,
    write_manifest,
)
from modelly.provenance.odd import odd_markdown
from modelly.provenance.runner import RunSpec, run_study
from modelly.provenance.verify import Verification, verify

__all__ = [
    "FORMAT",
    "MANIFEST_NAME",
    "BundleError",
    "Difference",
    "ManifestError",
    "RunSpec",
    "Tolerance",
    "Verification",
    "bundle",
    "first_difference",
    "odd_markdown",
    "read_manifest",
    "run_study",
    "verify",
    "write_manifest",
]
