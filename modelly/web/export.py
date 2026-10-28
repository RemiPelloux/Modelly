"""``export_web``: write a static site that runs a model in the browser with Pyodide.

The site is plain files, deployable on GitHub Pages or any static host::

    index.html, app.js, draw.js, worker.js, style.css   the runner page
    modelly.json                                         what to load and run
    wheels/modelly_abm-<version>-py3-none-any.whl        Modelly, pure Python
    model.zip                                            the model's code, unless it is
                                                         part of Modelly (an example, a
                                                         zoo model)

Pyodide itself comes from its CDN at the pinned ``PYODIDE_VERSION``, with only the
packages the model was seen to import (``modelly.web.packages``).
"""

from __future__ import annotations

import html
import importlib.util
import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import modelly
from modelly.profile.loader import TargetError
from modelly.studio.config import DEFAULT_SEED
from modelly.studio.loader import load_model_class, module_name
from modelly.web.packages import needed_packages, normalise
from modelly.web.runtime import describe
from modelly.web.wheel import EXCLUDED, FIXED_DATE, write_wheel

PYODIDE_VERSION = "314.0.7"
PYODIDE_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
DEFAULT_STEPS = 100
SITE_FILES = ("index.html", "app.js", "draw.js", "worker.js", "style.css")
SITE_DIR = Path(__file__).parent / "site"
MANIFEST = "modelly.json"
MODEL_ARCHIVE = "model.zip"
WHEELS = "wheels"
OWN_PACKAGE = "modelly"
TITLE_MARK = "{{title}}"


@dataclass(frozen=True)
class WebExport:
    """What ``export_web`` writes.

    Attributes:
        target: The model, ``path/to/model.py:Class`` or ``package.module:Class``.
        out: The folder the site is written to (created; files in it are replaced).
        steps: The steps the export runs the model for, to check it and to see what it
            imports; also the page's default run length.
        seed: The seed of that run and the page's default seed.
        title: The page title; the model class name when empty.
        wheel: A Modelly wheel to ship instead of the pure one built from this install,
            such as one built for WebAssembly with ``pyodide build``.
        pyodide_url: Where the page loads Pyodide from (the pinned CDN release).
        add_packages: Pyodide packages to load in addition to the detected ones.
        skip_packages: Detected packages not to load.
    """

    target: str
    out: Path
    steps: int = DEFAULT_STEPS
    seed: int = DEFAULT_SEED
    title: str = ""
    wheel: Path | None = None
    pyodide_url: str = PYODIDE_URL
    add_packages: tuple[str, ...] = field(default=())
    skip_packages: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class ModelCode:
    """Where a model's code is: its import name and the files the site ships for it."""

    module: str
    files: tuple[tuple[Path, str], ...] = ()
    keep: PurePosixPath | None = None


def _module_file(source: str) -> Path:
    """The file of module ``source``."""
    try:
        spec = importlib.util.find_spec(source)
    except ImportError as error:
        raise TargetError(f"cannot import {source!r}: {error}") from error
    if spec is None or spec.origin is None:
        raise TargetError(f"cannot find module {source!r}")
    return Path(spec.origin)


def model_code(target: str) -> ModelCode:
    """The import name of ``target``'s module and the files the site needs for it."""
    source = target.rpartition(":")[0]
    path = Path(source) if source.endswith(".py") else _module_file(source)
    root, dotted = module_name(path.resolve())
    parts = dotted.split(".")
    if parts[0] == OWN_PACKAGE:
        inside = PurePosixPath(*parts[1:-1]) if len(parts) > 2 else None
        keep = inside if inside is not None and inside.parts[0] in EXCLUDED else None
        return ModelCode(dotted, keep=keep)
    if len(parts) == 1:
        found = sorted(root.glob("*.py"))
    else:
        found = sorted(p for p in (root / parts[0]).rglob("*") if p.is_file())
    files = tuple(
        (p, p.relative_to(root).as_posix())
        for p in found
        if "__pycache__" not in p.parts
    )
    return ModelCode(dotted, files=files)


def _write_archive(path: Path, files: tuple[tuple[Path, str], ...]) -> None:
    """Zip ``files`` (source, name in the archive) into ``path``, deterministically."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for source, name in files:
            archive.writestr(
                zipfile.ZipInfo(name, date_time=FIXED_DATE), source.read_bytes()
            )


def _packages(options: WebExport) -> list[str]:
    """The Pyodide packages the page loads: detected, plus added, minus skipped."""
    found = needed_packages(options.target, options.steps, options.seed)
    skipped = {normalise(name) for name in options.skip_packages}
    wanted = {*found, *(normalise(name) for name in options.add_packages)}
    return sorted(wanted - skipped)


def _ship_wheel(options: WebExport, code: ModelCode) -> str:
    """Put the Modelly wheel into the site; its path relative to the site."""
    wheels = options.out / WHEELS
    if options.wheel is None:
        return f"{WHEELS}/{write_wheel(wheels, code.keep).name}"
    wheels.mkdir(parents=True, exist_ok=True)
    shutil.copy2(options.wheel, wheels / options.wheel.name)
    return f"{WHEELS}/{options.wheel.name}"


def _write_page(out: Path, title: str) -> None:
    """Copy the runner page into ``out``, with ``title`` in the HTML."""
    for name in SITE_FILES:
        text = (SITE_DIR / name).read_text(encoding="utf-8")
        if name == "index.html":
            text = text.replace(TITLE_MARK, html.escape(title))
        (out / name).write_text(text, encoding="utf-8")


def export_web(options: WebExport) -> dict[str, Any]:
    """Write the static site ``options`` describes; the manifest it wrote.

    Raises:
        TargetError: When the model cannot be found, built or run for ``steps`` steps.
    """
    code = model_code(options.target)
    model_class = load_model_class(options.target)
    packages = _packages(options)
    options.out.mkdir(parents=True, exist_ok=True)
    title = options.title or model_class.__name__
    manifest = {
        "title": title,
        "target": f"{code.module}:{model_class.__name__}",
        "modelly": modelly.__version__,
        "wheel": _ship_wheel(options, code),
        "model_archive": MODEL_ARCHIVE if code.files else None,
        "pyodide": {"version": PYODIDE_VERSION, "url": options.pyodide_url},
        "packages": packages,
        "parameters": describe(model_class),
        "seed": options.seed,
        "steps": options.steps,
    }
    if code.files:
        _write_archive(options.out / MODEL_ARCHIVE, code.files)
    _write_page(options.out, title)
    text = json.dumps(manifest, indent=2) + "\n"
    (options.out / MANIFEST).write_text(text, encoding="utf-8")
    return manifest


__all__ = ["PYODIDE_URL", "PYODIDE_VERSION", "WebExport", "export_web", "model_code"]
