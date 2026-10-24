"""Import optional geospatial libraries with an error that names the extra to install."""

from __future__ import annotations

import importlib
from types import ModuleType


def require(module: str, extra: str) -> ModuleType:
    """Import ``module``, or raise an ``ImportError`` naming the Modelly extra that provides it.

    Args:
        module: the module to import, for example ``"rasterio"``.
        extra: the optional dependency group of ``modelly-abm`` that installs it.
    """
    try:
        return importlib.import_module(module)
    except ImportError as e:
        raise ImportError(
            f"{module} is needed here and is not installed; install the '{extra}' "
            f'extra: pip install "modelly-abm[{extra}]"'
        ) from e
