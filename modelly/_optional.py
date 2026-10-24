"""Import optional dependencies lazily, with an error that names the extra to install."""

from __future__ import annotations

import importlib
from types import ModuleType

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
