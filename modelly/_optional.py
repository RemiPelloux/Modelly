"""Import optional dependencies lazily, with an error that names the extra to install."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any

DISTRIBUTION = "modelly-abm"


def require(module: str, extra: str) -> ModuleType:
    """Import ``module`` or raise an ImportError naming ``pip install modelly-abm[extra]``.

    Example:
        >>> pa = require("pyarrow", "experiments")  # doctest: +SKIP
    """
    try:
        return importlib.import_module(module)
    except ImportError as error:
        raise ImportError(
            f"{module} is needed for this feature: "
            f'pip install "{DISTRIBUTION}[{extra}]"'
        ) from error


def lazy_exports(
    package: str, modules: dict[str, str]
) -> tuple[Callable[[str], Any], Callable[[], list[str]]]:
    """A module ``__getattr__`` and ``__dir__`` that import each public name on first use.

    ``modules`` maps each name to the module it lives in. The value is stored in the
    package's namespace, so the import runs once.

    Example:
        >>> __getattr__, __dir__ = lazy_exports(__name__, {"Thing": "pkg.things"})  # doctest: +SKIP
    """
    namespace = vars(sys.modules[package])

    def attribute(name: str) -> Any:
        if name not in modules:
            raise AttributeError(f"module {package!r} has no attribute {name!r}")
        value = getattr(importlib.import_module(modules[name]), name)
        namespace[name] = value
        return value

    def names() -> list[str]:
        return sorted({*namespace, *modules})

    return attribute, names


class LazyModule:
    """A stand-in for a module that imports it on the first attribute read.

    Keeps heavy dependencies such as pandas out of ``import modelly``: write
    ``pd = LazyModule("pandas")`` at module level (with the real import under
    ``TYPE_CHECKING``) and ``pd.DataFrame`` imports pandas when first used.
    """

    __slots__ = ("_module", "_name")

    def __init__(self, name: str) -> None:
        self._name = name
        self._module: ModuleType | None = None

    def __getattr__(self, attribute: str) -> Any:
        module = self._module
        if module is None:
            module = self._module = importlib.import_module(self._name)
        return getattr(module, attribute)


def is_series(value: object) -> bool:
    """Whether ``value`` is a pandas Series, without importing pandas."""
    pandas = sys.modules.get("pandas")
    return pandas is not None and isinstance(value, pandas.Series)
