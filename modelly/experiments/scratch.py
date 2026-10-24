"""A temporary results folder that lives as long as the object that asked for it."""

from __future__ import annotations

import shutil
import tempfile
import weakref
from pathlib import Path


def scratch_folder(owner: object, prefix: str) -> Path:
    """A new temporary folder, removed when ``owner`` is garbage-collected or at exit.

    ``tempfile.TemporaryDirectory`` would do the same but warns (``ResourceWarning``) when it
    is cleaned up implicitly; here implicit clean-up is the intended life cycle.
    """
    folder = Path(tempfile.mkdtemp(prefix=prefix))
    weakref.finalize(owner, shutil.rmtree, folder, ignore_errors=True)
    return folder
