"""Sphinx conf for a tag whose docs/conf.py predates the version switcher (v1.0, v1.1).

scripts/build-docs-version.sh passes this folder as ``sphinx-build -c``: it runs the
tag's own conf.py, makes its folder-relative paths absolute, then applies this
branch's docs/versioning.py, so every published version has the same switcher.
"""

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TAG_CONF = Path(os.environ["MODELLY_TAG_CONF"]).resolve()
_TAG_DOCS = _TAG_CONF.parent

__file__ = str(_TAG_CONF)  # the tag's conf.py resolves its folder from __file__
exec(compile(_TAG_CONF.read_text(), __file__, "exec"))  # noqa: S102

templates_path = [str(_TAG_DOCS / p) for p in globals().get("templates_path", [])]
html_static_path = [str(_TAG_DOCS / p) for p in globals().get("html_static_path", [])]
html_logo = str(_TAG_DOCS / html_logo)  # noqa: F821  (defined by the tag's conf.py)
html_favicon = str(_TAG_DOCS / html_favicon)  # noqa: F821

sys.path.insert(0, str(_HERE.parent.parent / "docs"))
from versioning import apply_versioning  # noqa: E402

apply_versioning(globals())
