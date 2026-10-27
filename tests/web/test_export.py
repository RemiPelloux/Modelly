"""Tests for ``modelly export-web``: the static site it writes."""

import json
import zipfile

import pytest

from modelly.__main__ import main as modelly_main
from modelly.web.__main__ import main
from modelly.web.export import (
    MANIFEST,
    MODEL_ARCHIVE,
    PYODIDE_URL,
    PYODIDE_VERSION,
    SITE_FILES,
    WebExport,
    export_web,
    model_code,
)
from modelly.web.packages import CORE

SCHELLING = "modelly.examples.basic.schelling.model:Schelling"
FOREST_FIRE = "modelly.zoo.forest_fire.model:ForestFire"
STEPS = 2
MODEL_SOURCE = '''"""A tiny model."""

from modelly import Model


class Tiny(Model):
    """Nothing happens, {name}."""

    def __init__(self, size: int = 3, rng=None):
        """Keep ``size``."""
        super().__init__(rng=rng)
        self.size = size
'''


def write_model(folder, name, package=True):
    """A model file ``name``/model.py (a package when ``package``); its target."""
    code = folder / name
    code.mkdir(parents=True)
    if package:
        (code / "__init__.py").write_text("", encoding="utf-8")
    (code / "model.py").write_text(MODEL_SOURCE.format(name=name), encoding="utf-8")
    (code / "notes.txt").write_text("data", encoding="utf-8")
    return f"{code / 'model.py'}:Tiny"


def test_example_site(tmp_path):
    """An example ships in the wheel: page, manifest, wheel, no model archive."""
    out = tmp_path / "site"
    manifest = export_web(WebExport(SCHELLING, out, steps=STEPS, title="<Segregation>"))
    assert {p.name for p in out.iterdir()} == {*SITE_FILES, MANIFEST, "wheels"}
    assert json.loads((out / MANIFEST).read_text(encoding="utf-8")) == manifest
    assert manifest["target"] == SCHELLING
    assert manifest["model_archive"] is None
    assert manifest["packages"] == sorted(CORE)
    assert manifest["pyodide"] == {"version": PYODIDE_VERSION, "url": PYODIDE_URL}
    assert manifest["steps"] == STEPS
    assert {p["name"] for p in manifest["parameters"]} >= {"density", "homophily"}
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "&lt;Segregation&gt; · Modelly" in page
    with zipfile.ZipFile(out / manifest["wheel"]) as wheel:
        assert "modelly/examples/basic/schelling/model.py" in wheel.namelist()


def test_zoo_model_needs_no_example(tmp_path):
    """A zoo model is part of the trimmed wheel already."""
    manifest = export_web(WebExport(FOREST_FIRE, tmp_path, steps=STEPS))
    assert manifest["title"] == "ForestFire"
    with zipfile.ZipFile(tmp_path / manifest["wheel"]) as wheel:
        names = wheel.namelist()
    assert "modelly/zoo/forest_fire/model.py" in names
    assert not any(name.startswith("modelly/examples/") for name in names)


def test_user_package_goes_into_the_model_archive(tmp_path):
    """A model in a package ships that package; the target uses its dotted name."""
    target = write_model(tmp_path / "project", "webpkg_one")
    out = tmp_path / "site"
    manifest = export_web(WebExport(target, out, steps=STEPS))
    assert manifest["target"] == "webpkg_one.model:Tiny"
    assert manifest["model_archive"] == MODEL_ARCHIVE
    with zipfile.ZipFile(out / MODEL_ARCHIVE) as archive:
        assert sorted(archive.namelist()) == [
            "webpkg_one/__init__.py",
            "webpkg_one/model.py",
            "webpkg_one/notes.txt",
        ]
    size = next(p for p in manifest["parameters"] if p["name"] == "size")
    assert size == {"name": "size", "kind": "int", "default": 3, "choices": []}


def test_single_file_ships_the_python_files_next_to_it(tmp_path):
    """A model outside a package ships the .py files of its folder only."""
    target = write_model(tmp_path, "webfile_two", package=False)
    assert model_code(target).module == "model"
    names = [name for _, name in model_code(target).files]
    assert names == ["model.py"]


def test_added_and_skipped_packages_and_a_given_wheel(tmp_path):
    """--package and --skip-package edit the detected list; --wheel is copied."""
    wheel = tmp_path / "modelly_abm-0-cp314-cp314-pyemscripten_2026_0_wasm32.whl"
    wheel.write_bytes(b"wheel")
    options = WebExport(
        SCHELLING,
        tmp_path / "site",
        steps=STEPS,
        wheel=wheel,
        add_packages=("Networkx",),
        skip_packages=("six",),
    )
    manifest = export_web(options)
    assert "networkx" in manifest["packages"]
    assert "six" not in manifest["packages"]
    assert manifest["wheel"] == f"wheels/{wheel.name}"
    assert (tmp_path / "site" / manifest["wheel"]).read_bytes() == b"wheel"


def test_cli_writes_the_site(tmp_path, capsys):
    """``modelly export-web`` reports the target and the packages."""
    out = tmp_path / "site"
    argv = ["export-web", SCHELLING, "--out", str(out), "--steps", str(STEPS)]
    assert modelly_main(argv) == 0
    assert "numpy, pandas" in capsys.readouterr().out
    assert (out / "worker.js").is_file()


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["nope.py:Model"], "no such file"),
        ([SCHELLING, "--wheel", "x.whl"], "no such wheel"),
    ],
)
def test_cli_usage_errors(argv, message, capsys, tmp_path):
    """A missing model or wheel is a usage error."""
    assert main([*argv, "--out", str(tmp_path)]) == 2
    assert message in capsys.readouterr().err


def test_cli_rejects_zero_steps(capsys):
    """--steps must be at least one."""
    with pytest.raises(SystemExit) as stop:
        main([SCHELLING, "--steps", "0"])
    assert stop.value.code == 2
    assert "positive" in capsys.readouterr().err


def test_cli_model_error(tmp_path, capsys):
    """A model that raises while it runs exits with 1 and its traceback."""
    path = tmp_path / "failing_model.py"
    path.write_text(
        "from modelly import Model\n\n\nclass Failing(Model):\n"
        "    def step(self):\n        raise ValueError('step failed')\n",
        encoding="utf-8",
    )
    assert main([f"{path}:Failing", "--out", str(tmp_path / "site")]) == 1
    assert "step failed" in capsys.readouterr().err
