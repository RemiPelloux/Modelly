"""Helpers for the NetLogo translator tests: bundled sources and loading a translation."""

import importlib.util
from importlib.resources import files
from itertools import count
from pathlib import Path

from modelly.netlogo import Translation, translate

_modules = count()


def bundled(stem: str) -> str:
    """The NetLogo source of a bundled model (``fire`` or ``wolf_sheep``)."""
    path = files("modelly.netlogo").joinpath("models", f"{stem}.nlogo")
    return path.read_text(encoding="utf-8")


def load(translation: Translation, folder: Path):
    """Write ``translation`` to a file in ``folder`` and import it as a fresh module."""
    name = f"translated_{next(_modules)}"
    path = folder / f"{name}.py"
    path.write_text(translation.source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def translated(stem: str, folder: Path):
    """The bundled model ``stem``, translated and imported."""
    return load(translate(bundled(stem), stem), folder)
