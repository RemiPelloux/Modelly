"""Find the model class and the portrayal a ``modelly studio`` command line names.

A ``path/to/model.py`` is imported under its package's dotted name when its folders are
packages (``modelly/examples/basic/schelling/model.py`` is
``modelly.examples.basic.schelling.model``), else under its own name with its folder on
``sys.path``. Either way the classes are importable by name, so checkpoints of the model
load again, and a model's ``from agents import Sheep`` finds the file next to it.
"""

from __future__ import annotations

import importlib
import inspect
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

from modelly.core.model import Model
from modelly.profile.loader import TargetError

INIT = "__init__.py"


def module_name(path: Path) -> tuple[Path, str]:
    """The folder to put on ``sys.path`` and the dotted name to import ``path`` by."""
    parts = [path.stem]
    folder = path.parent
    while (folder / INIT).is_file():
        parts.insert(0, folder.name)
        folder = folder.parent
    return folder, ".".join(parts)


def import_source(source: str) -> ModuleType:
    """Import ``source``: a ``.py`` file or a dotted module name.

    Raises:
        TargetError: When the file does not exist or the module cannot be imported.
    """
    path = Path(source)
    if path.suffix == ".py":
        if not path.is_file():
            raise TargetError(f"no such file: {source}")
        root, source = module_name(path.resolve())
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
    try:
        return importlib.import_module(source)
    except ImportError as error:
        raise TargetError(f"cannot import {source!r}: {error}") from error


def _split(target: str, what: str) -> tuple[str, str]:
    """``source:name`` to ``(source, name)``."""
    source, sep, name = target.rpartition(":")
    if not sep or not source or not name:
        raise TargetError(
            f"expected path/to/file.py:{what} or package.module:{what}, got {target!r}"
        )
    return source, name


def load_model_class(target: str) -> type[Model]:
    """The Model subclass ``path/to/model.py:Class`` or ``package.module:Class`` names.

    Raises:
        TargetError: When it cannot be found or is not a Model subclass.
    """
    source, name = _split(target, "ModelClass")
    cls = getattr(import_source(source), name, None)
    if not (inspect.isclass(cls) and issubclass(cls, Model)):
        raise TargetError(f"{name!r} in {source} is not a Model subclass")
    return cls


def load_portrayal(target: str) -> Callable:
    """The agent portrayal function ``path/to/app.py:function`` names.

    Raises:
        TargetError: When it cannot be found or is not callable.
    """
    source, name = _split(target, "function")
    function = getattr(import_source(source), name, None)
    if not callable(function):
        raise TargetError(f"{name!r} in {source} is not a function")
    return function


__all__ = ["import_source", "load_model_class", "load_portrayal", "module_name"]
