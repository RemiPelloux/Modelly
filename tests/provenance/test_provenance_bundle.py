"""``bundle``: contents, byte-determinism, and a bundle that verifies once unpacked."""

import json
import zipfile

import pytest

from modelly.provenance import BundleError, bundle, verify
from modelly.provenance.bundle import FIXED_TIME

EXPECTED = {
    ".zenodo.json",
    "CITATION.cff",
    "agents.parquet",
    "code/agents.py",
    "code/model.py",
    "inputs/scenario.toml",
    "manifest.json",
    "model.parquet",
    "requirements.lock",
    "seeds.json",
}


def _names(path):
    """Archive entry names, with the format of the outputs normalised to parquet."""
    with zipfile.ZipFile(path) as archive:
        return [name.replace(".csv", ".parquet") for name in archive.namelist()]


def test_bundle_contents(boltzmann_run, tmp_path):
    """Manifest, outputs, code, inputs, lock, seeds and archive metadata."""
    path = bundle(boltzmann_run, tmp_path / "study.zip")
    names = _names(path)
    assert names == sorted(names)
    assert set(names) >= EXPECTED
    with zipfile.ZipFile(path) as archive:
        assert all(info.date_time == FIXED_TIME for info in archive.infolist())
        manifest = json.loads(archive.read("manifest.json"))
        zenodo = json.loads(archive.read(".zenodo.json"))
        lock = archive.read("requirements.lock").decode("utf-8")
    assert manifest["code"]["root"] == "code"
    assert manifest["scenario"]["file"] == "inputs/scenario.toml"
    assert zenodo["upload_type"] == "dataset" and "TODO" in zenodo["title"]
    assert "numpy==" in lock


def test_bundle_is_byte_deterministic(boltzmann_run, tmp_path):
    """The same run bundled twice gives the same bytes."""
    first = bundle(boltzmann_run, tmp_path / "a.zip").read_bytes()
    second = bundle(boltzmann_run / "manifest.json", tmp_path / "b.zip").read_bytes()
    assert first == second


def test_unpacked_bundle_verifies(boltzmann_run, tmp_path):
    """A reviewer unpacks the archive elsewhere and the outputs match."""
    path = bundle(boltzmann_run, tmp_path / "study.zip")
    target = tmp_path / "review"
    with zipfile.ZipFile(path) as archive:
        archive.extractall(target)
    result = verify(target / "manifest.json")
    assert result.matches
    assert result.notes == []


def test_changed_output_cannot_be_bundled(boltzmann_run, tmp_path):
    """Outputs edited after the run are refused."""
    output = next(p for p in boltzmann_run.iterdir() if p.stem == "model")
    output.write_bytes(output.read_bytes() + b"\0")
    with pytest.raises(BundleError, match="changed since the run"):
        bundle(boltzmann_run, tmp_path / "study.zip")
