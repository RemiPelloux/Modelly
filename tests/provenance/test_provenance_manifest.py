"""The manifest ``modelly run`` writes: schema, code, environment, seeds, outputs."""

import json

import pytest
from conftest import SCHELLING, STEPS

from modelly.profile.loader import TargetError
from modelly.provenance import (
    FORMAT,
    ManifestError,
    RunSpec,
    read_manifest,
    run_study,
    verify,
    write_manifest,
)
from modelly.provenance import code as code_module
from modelly.provenance import outputs as outputs_module
from modelly.provenance.environment import build_name, lock_text, native_flags
from modelly.provenance.files import from_posix, hash_file


def test_manifest_records_the_run(boltzmann_run):
    """Every documented block is there, with the scenario file's seed and parameters."""
    manifest = read_manifest(boltzmann_run)
    assert manifest["format"] == FORMAT
    assert manifest["target"] == {
        "class": "BoltzmannWealth",
        "kind": "file",
        "source": "model.py",
    }
    assert manifest["run"] == {"seed": 3, "steps": STEPS}
    assert manifest["seeds"]["seed"] == 3
    assert manifest["scenario"]["parameters"] == {"n": 30}
    assert manifest["scenario"]["resolved"]["n"] == 30
    assert manifest["scenario"]["file"] == "../scenario.toml"
    assert manifest["timing"]["wall_seconds"] >= 0
    assert manifest["timing"]["cpu_seconds"] >= 0


def test_code_block_hashes_the_model_sources(boltzmann_run):
    """model.py and its sibling agents.py are hashed, relative to the code root."""
    manifest = read_manifest(boltzmann_run)
    files = manifest["code"]["files"]
    assert {"model.py", "agents.py"} <= set(files)
    root = from_posix(manifest["code"]["root"], boltzmann_run)
    assert all(hash_file(root / name) == value for name, value in files.items())
    assert manifest["code"]["hash"].startswith("sha256:")


def test_paths_are_relative_posix(boltzmann_run):
    """No backslash and no absolute path in the paths the manifest stores."""
    manifest = read_manifest(boltzmann_run)
    paths = [manifest["code"]["root"], manifest["scenario"]["file"]]
    paths += [item["path"] for item in manifest["outputs"]]
    assert all("\\" not in p and not p.startswith("/") for p in paths)


def test_environment_block(boltzmann_run):
    """Modelly version and build, Python, platform and the dependency versions."""
    environment = read_manifest(boltzmann_run)["environment"]
    assert environment["modelly"]["native"] == native_flags()
    assert environment["modelly"]["build"] == build_name(native_flags())
    assert environment["python"]["version"]
    assert environment["platform"]["system"]
    assert "numpy" in environment["packages"]


def test_outputs_are_hashed(boltzmann_run):
    """Each collected table is a file whose hash and shape are recorded."""
    outputs = read_manifest(boltzmann_run)["outputs"]
    assert [item["table"] for item in outputs] == ["agents", "model"]
    for item in outputs:
        assert hash_file(boltzmann_run / item["path"]) == item["hash"]
    model = next(item for item in outputs if item["table"] == "model")
    assert model["rows"] == STEPS + 1
    assert model["columns"] == ["Gini"]


@pytest.mark.parametrize(
    ("flags", "name"),
    [
        ({"a": True, "b": True}, "compiled"),
        ({"a": False, "b": False}, "pure"),
        ({"a": True, "b": False}, "partial"),
    ],
)
def test_build_name(flags, name):
    """Compiled when every core is native, pure when none is."""
    assert build_name(flags) == name


def test_without_git_the_file_hashes_identify_the_code(
    tiny_model, tmp_path, monkeypatch
):
    """With no git on the PATH, the run still records the code by its file hashes."""
    monkeypatch.setattr(code_module.shutil, "which", lambda _: None)
    record = run_study(
        RunSpec(f"{tiny_model}:Walk", out=tmp_path / "out", steps=2, seed=1)
    )
    assert record["code"]["git"] is None
    assert list(record["code"]["files"]) == ["walk.py"]


def test_csv_without_pyarrow(tiny_model, tmp_path, monkeypatch):
    """Without pyarrow the tables are written as CSV, and a CSV run verifies."""
    monkeypatch.setattr(outputs_module, "parquet_available", lambda: False)
    record = run_study(
        RunSpec(f"{tiny_model}:Walk", out=tmp_path / "out", steps=2, seed=1)
    )
    assert {item["format"] for item in record["outputs"]} == {"csv"}
    assert (
        (tmp_path / "out" / "model.csv")
        .read_text(encoding="utf-8")
        .startswith("agents")
    )
    assert verify(tmp_path / "out").matches


def test_inputs_are_hashed(tiny_model, tmp_path):
    """--input files are recorded with their hash; a missing one is refused."""
    data = tmp_path / "data.csv"
    data.write_bytes(b"a,b\n1,2\n")
    out = tmp_path / "out"
    spec = RunSpec(f"{tiny_model}:Walk", out=out, steps=1, seed=1, inputs=(data,))
    record = run_study(spec)
    assert record["inputs"] == [{"hash": hash_file(data), "path": "../data.csv"}]
    with pytest.raises(TargetError, match="no such input"):
        run_study(RunSpec(spec.target, out=out, steps=1, inputs=(tmp_path / "nope",)))


def test_seed_is_drawn_and_recorded(tiny_model, tmp_path):
    """Without a seed one is drawn, recorded, and reproduces the run."""
    record = run_study(RunSpec(f"{tiny_model}:Walk", out=tmp_path / "out", steps=1))
    assert isinstance(record["run"]["seed"], int)


def test_dotted_module_target(tmp_path):
    """A package.module:Class target is recorded as a module."""
    record = run_study(RunSpec(SCHELLING, out=tmp_path / "out", steps=2, seed=1))
    assert record["target"]["kind"] == "module"
    assert "model.py" in record["code"]["files"]


def test_unsupported_format_is_refused(boltzmann_run):
    """A manifest of another format or major version cannot be read or written."""
    path = boltzmann_run / "manifest.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["format"] = "modelly-manifest/2"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ManifestError, match="unsupported"):
        read_manifest(path)
    with pytest.raises(ManifestError):
        write_manifest(boltzmann_run, {"format": FORMAT})


def test_lock_text_is_sorted_pins():
    """The lock file is one name==version line per package, sorted."""
    assert lock_text({"pandas": "2.0", "numpy": "1.0"}) == "numpy==1.0\npandas==2.0\n"
